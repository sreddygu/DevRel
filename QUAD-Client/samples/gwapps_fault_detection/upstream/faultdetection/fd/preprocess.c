/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <math.h>
#include <sys/time.h>
#include "preprocess.h"
#include "fault_detection.h"
#include "debugging.h"
#include "log_capture.h"
#include "model_inferencing.h"

// normalize variables
#define NORMALIZE_MAX_LEN 100
// cloud
#define R(idx)   (diff[(diff_idx) + (idx)])

// Static variables for tracking reference wifistat capture state
static int reference_wifistats_captured = 0;

// These were static in fault_detection.c, but used across calls to pre_process
// so they should remain static here.
static float *prev_itr = NULL;
static float *cur_itr = NULL;
static float *input_vec = NULL;

int get_file_length(const char *filename) {
        FILE *file = fopen(filename, "r");
        if (!file) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"Failed to open file");
                return -1;
        }
        int count = 0;
        float temp;
        while (fscanf(file, "%e", &temp) == 1) {
                if (count >= MODEL_VEC_LEN) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Error encountered while getting length of normalization files");
                        break;
                }
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "count: %d\n", count);
                count++;
        }
        fclose(file);
        return count;
}

void load_values(const char *filename, float *array, int len) {
    FILE *file = fopen(filename, "r");
    if (!file) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to open file");
        return;
    }
    int i = 0;
    while (i < len && fscanf(file, "%f", &array[i]) == 1) {
        i++;
    }
    if (i != len) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Warning: Expected %d values, but read %d from %s\n", len, i, filename);
    }
    fclose(file);
}

float normalize(int band, float val, int index) {
    static int MIN_MAX_LEN = -1;
    static float min_2g[NORMALIZE_MAX_LEN], max_2g[NORMALIZE_MAX_LEN];
    static float min_5g[NORMALIZE_MAX_LEN], max_5g[NORMALIZE_MAX_LEN];
    static float min_6g[NORMALIZE_MAX_LEN], max_6g[NORMALIZE_MAX_LEN];
    static int initialized = 0;

    if (!initialized) {
        MIN_MAX_LEN = get_file_length("/etc/fd/data/WIN-NW-FD-AE-2G_max.txt");
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"MIN_MAX_LEN = %d\n", MIN_MAX_LEN);

        load_values("/etc/fd/data/WIN-NW-FD-AE-2G_min.txt", min_2g, MIN_MAX_LEN);
        load_values("/etc/fd/data/WIN-NW-FD-AE-2G_max.txt", max_2g, MIN_MAX_LEN);
        load_values("/etc/fd/data/WIN-NW-FD-AE-5G_min.txt", min_5g, MIN_MAX_LEN);
        load_values("/etc/fd/data/WIN-NW-FD-AE-5G_max.txt", max_5g, MIN_MAX_LEN);
        load_values("/etc/fd/data/WIN-NW-FD-AE-6G_min.txt", min_6g, MIN_MAX_LEN);
        load_values("/etc/fd/data/WIN-NW-FD-AE-6G_max.txt", max_6g, MIN_MAX_LEN);

        initialized = 1;
    }

    if (index >= MIN_MAX_LEN) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Index %d out of bounds (max %d)\n", index, MIN_MAX_LEN - 1);
        return 0;
    }

    float min_val = 0, max_val = 0;
    switch (band) {
        case 2:
            min_val = min_2g[index];
            max_val = max_2g[index];
            break;
        case 5:
            min_val = min_5g[index];
            max_val = max_5g[index];
            break;
        case 6:
            min_val = min_6g[index];
            max_val = max_6g[index];
            break;
        default:
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"Wrong Band %d\n", band);
            return 0;
    }

    float dnom = max_val - min_val;
    float normalized = 0.0;

    if (dnom == 0) {

        if (debug_lvl == 1) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"Warning: Zero range for band %d at index %d (min = %f, max = %f)\n", band, index, min_val, max_val);
        }
        normalized = 0.0;
    } else {
        normalized = (val - min_val) / dnom;
    }

    if (debug_lvl == 1) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Band %d - idx: %d: value %f normalized to %f (min: %f, max: %f)\n", band, index, val, normalized, min_val, max_val);
    }

    return normalized;
}

void pre_process(int radio_cnt, float * all_stats, int interval)
{
	int total_stats = (radio_cnt * CRITICAL_STAT_LEN);
	int i = 0, rad = 0;
	int band_check = 0;
	int cur_anom_cnt = 0;

 	sys_log_avail = 0;
	memset(cur_sys_path, '0', PATH_MAX);
	for(band_check = 0; band_check < radio_cnt; band_check++){
		if(cur_bands[band_check] != BAND_2G && cur_bands[band_check] != BAND_5G && cur_bands[band_check] != BAND_6G){
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"Radio Bands array corrupted! Radio#%d is %d band\n", band_check, cur_bands[band_check]);
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"Ignore next inference\n");
			return;
		}
	}

	if(prev_itr == NULL){
		if(debug_lvl == 1){
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"1st iteration, Total stats:%d\n", total_stats);
		}
		prev_itr = (float *) malloc(total_stats * sizeof(float));
		for(i = 0; i < total_stats; i++){
			prev_itr[i] = all_stats[i];
		}

		// Capture reference wifistats during first timestamp for each band
		if (!reference_wifistats_captured) {
			for (int rad_id = 0; rad_id < radio_cnt; rad_id++) {
				int band = cur_bands[rad_id];
				char *band_reference_path = NULL;
				
				if (band == BAND_2G) {
					band_reference_path = reference_wifistat_path_2g;
				} else if (band == BAND_5G) {
					band_reference_path = reference_wifistat_path_5g;
				} else if (band == BAND_6G) {
					band_reference_path = reference_wifistat_path_6g;
				}
				
				if (band_reference_path && band_reference_path[0] == '\0') {
					// Set the reference path for this band
					snprintf(band_reference_path, CMD_LEN, "%sreference_wifistats_%dG.txt", log_dir, band);
					
                        // Capture the reference wifistats (no packet log during reference capture)
                        if (capture_wifistats_to_file(rad_id, band_reference_path, 0) == 0) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Captured reference wifistats for %dG band at first timestamp: %s\n", 
                                        band, band_reference_path);
                        } else {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to capture reference wifistats for %dG band\n", band);
                        }
				}
			}
			reference_wifistats_captured = 1;
		}

		return;
	} else {
		if (cur_itr == NULL)
			cur_itr = (float *) malloc(total_stats * sizeof(float));
		for (i = 0; i < total_stats; i++) {
                	cur_itr[i] = all_stats[i];
		}
	}
	float * diff = (float *) malloc(total_stats * sizeof(float));
	int anomaly_itr = itr_cnt % max_anomaly_count;
	if(debug_lvl == 1) {
               log_message(LOG_LEVEL_AD_LIB_DEBUG,"===Current inference iteration: %d===\n", itr_cnt);
        }
	anomaly_history[anomaly_itr] = 0;
	for(int idx = 0; idx < total_stats; idx++)
	{
		diff[idx] = (cur_itr[idx] - prev_itr[idx]) / interval;
		if(debug_lvl == 1) {
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"==index %d %f - %f / %d = %f ==\n", idx, cur_itr[idx], prev_itr[idx], interval, diff[idx]);
		}
	}
	if(debug_lvl == 1){
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"Create input vec\n");
	}

	int all_rad_cli = 0;
        float all_cli_change = 0;
        for(rad = 0; rad < radio_cnt; rad++) {
                int cli_idx = CLIENTS_IDX + (CRITICAL_STAT_LEN * rad);
                all_rad_cli += cur_itr[cli_idx];
        }
        all_cli_change =  all_rad_cli - prev_cli_count;
        prev_cli_count = all_rad_cli;

        float sum_tx1_tx3_m3_success_rate_of_change = 0;
        for(rad = 0; rad < radio_cnt; rad++) {
                int temp_diff_idx = rad * CRITICAL_STAT_LEN;
                sum_tx1_tx3_m3_success_rate_of_change += diff[temp_diff_idx + TX_MG_1];
                sum_tx1_tx3_m3_success_rate_of_change += diff[temp_diff_idx + TX_MG_3];
                sum_tx1_tx3_m3_success_rate_of_change += diff[temp_diff_idx + M3_SUCCESS_IDX];

                log_message(LOG_LEVEL_AD_LIB_DEBUG, "sum_tx1_tx3_m3_success_rate_of_change: %f\n", sum_tx1_tx3_m3_success_rate_of_change);
        }

	input_vec = (float *) malloc(INPUT_VEC_LEN * radio_cnt * sizeof(float));

        for (rad = 0; rad < radio_cnt; rad++) {
                int input_idx = rad * INPUT_VEC_LEN;
                int diff_idx = rad * CRITICAL_STAT_LEN;

                // get_total_beacon_failure_frames()
                float total_beacon_fail_frames = 0;
                for (int k = HW_0_ST + 1; k <= HW_0_END; k++) {
                        total_beacon_fail_frames += R(k);
                }

                // get_total_management_frames() - we skip 7
                float total_management_frames = 0;
                for (int k = HW_4_ST + 1; k <= HW_4_END; k++) {
                        if (k != (HW_4_ST + 7)) {
                                total_management_frames += R(k);
                        } 
                }

                // calculate beacon_fail_rate
                float beacon_fail_rate = 0;
                float beacon_denom = total_beacon_fail_frames + R(HW_0_ST);
                if (beacon_denom != 0) {
                        beacon_fail_rate = total_beacon_fail_frames / beacon_denom;
                } else {
                        beacon_fail_rate = 0;
                }

                // calculate data_retry_pct
                float data_rtry_pct = 0;
                float data_fail_frames = R(TX_XRET_IDX) - (total_beacon_fail_frames + total_management_frames);
                float data_success_frames = R(PPDU_OK_IDX) - (R(HW_0_ST) + R(HW_4_ST));

                // fail-safe values for data_fail_frames, data_success_frames
                if (data_fail_frames < NFZERO) data_fail_frames = 0;
                if (data_success_frames < NFZERO) data_success_frames = 0;

                float total_frames = data_fail_frames + data_success_frames;

                // fail-safe values for data_rtry_pct
                if (cur_bands[rad] == BAND_6G) {
                        if (total_frames < 6) data_rtry_pct = 0;
                }
                if (total_frames < 5) {
                        data_rtry_pct = 0;
                } else if (total_frames == 0) {
                        data_rtry_pct = 0;
                } else {
                        data_rtry_pct = data_fail_frames / total_frames;
                }

                // calculate client disconnect
                float client_change = R(CLIENTS_IDX);
                // total number of clients in current band
                float clients_per_band = cur_itr[diff_idx + CLIENTS_IDX];

                // calculate fail to connect
                float m1_success_rate = 0, m3_success_rate = 0, m1_m3_rate = 0;
                float tx1_tx11 = 0.25, rx0_rx11 = 0.25, tx1_rx0 = 1, tx11_rx11 = 1;

                float m1_success_raw = cur_itr[diff_idx + M1_SUCCESS_IDX];
                float m1_packet_raw = cur_itr[diff_idx + M1_PACKET_IDX];
                float m3_success_raw = cur_itr[diff_idx + M3_SUCCESS_IDX];
                float m3_packet_raw = cur_itr[diff_idx + M3_PACKET_IDX];

                float m3_success_rate_of_change = R(M3_SUCCESS_IDX);
                float tx_mgmt_3 = R(TX_MG_3);

                float tx_1_raw = cur_itr[diff_idx + TX_MG_1];
                float tx_11_raw = cur_itr[diff_idx + TX_MG_11];

                float rx_0_raw  = cur_itr[diff_idx + FW_RX_MGMT_IDX];
                float rx_11_raw = cur_itr[diff_idx + RX_MG_11];

                if (!isnan(R(M1_PACKET_IDX)) && R(M1_PACKET_IDX) != 0) {
                        m1_success_rate = R(M1_SUCCESS_IDX) / R(M1_PACKET_IDX);
                }
                if (!isnan(R(M3_PACKET_IDX)) && R(M3_PACKET_IDX) != 0) {
                        m3_success_rate = R(M3_SUCCESS_IDX) / R(M3_PACKET_IDX);
                }
                if (!isnan(R(M3_SUCCESS_IDX)) && R(M3_SUCCESS_IDX) != 0) {
                        m1_m3_rate = R(M1_SUCCESS_IDX) / R(M3_SUCCESS_IDX);
                }                

                float rx_0  = R(FW_RX_MGMT_IDX);
                float rx_11 = R(RX_MG_11);
                float rx_12 = R(RX_MG_12);
                float tx_1  = R(TX_MG_1);
                float tx_11 = R(TX_MG_11);
                float tx_12 = R(TX_MG_12);
                float tx_3 = R(TX_MG_3);

                if (tx_11 != 0) {
                        tx1_tx11 = tx_1 / tx_11;
                }
                if (rx_11 != 0) {
                        rx0_rx11  = rx_0 / rx_11;
                        tx11_rx11 = tx_11 / rx_11;
                }
                if (rx_0 != 0) {
                        tx1_rx0 = tx_1 / rx_0;
                }

                int m1_success_rate_pro = (m1_success_rate < PFZERO) && ((tx_11 > 0) || (rx_11 > 0));
                int m3_success_rate_pro = (m3_success_rate < PFZERO) && ((tx_11 > 0) || (rx_11 > 0));

                int is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive = ((tx_12 > 0) || (rx_12 > 0)) && (tx_1 <= 0) && (tx_3 <= 0) && (m3_success_rate_of_change <= 0);

                int is_tx12_or_rx12_active_and_tx1_active = ((tx_12 > 0) || (rx_12 > 0)) && (sum_tx1_tx3_m3_success_rate_of_change > PFZERO);

                // model input
                input_vec[input_idx++] = beacon_fail_rate;
                input_vec[input_idx++] = data_rtry_pct;
                input_vec[input_idx++] = tx_1;
                input_vec[input_idx++] = tx_11;
                input_vec[input_idx++] = tx1_tx11;
                input_vec[input_idx++] = rx0_rx11;
                input_vec[input_idx++] = tx1_rx0;
                input_vec[input_idx++] = tx11_rx11;
                input_vec[input_idx++] = m1_success_rate_pro;
                input_vec[input_idx++] = m3_success_rate_pro;
                input_vec[input_idx++] = m1_m3_rate;
                input_vec[input_idx++] = is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive;
                input_vec[input_idx++] = is_tx12_or_rx12_active_and_tx1_active;
                input_vec[input_idx++] = all_cli_change;
                // rule based checks
                input_vec[input_idx++] = beacon_fail_rate;
                input_vec[input_idx++] = data_rtry_pct;
                input_vec[input_idx++] = tx_1;
                input_vec[input_idx++] = tx_11;
                input_vec[input_idx++] = tx1_tx11;
                input_vec[input_idx++] = rx0_rx11;
                input_vec[input_idx++] = tx1_rx0;
                input_vec[input_idx++] = tx11_rx11;
                input_vec[input_idx++] = m1_success_rate_pro;
                input_vec[input_idx++] = m3_success_rate_pro;
                input_vec[input_idx++] = m1_m3_rate;
                input_vec[input_idx++] = all_cli_change;
                input_vec[input_idx++] = client_change;
                input_vec[input_idx++] = tx_12;
                input_vec[input_idx++] = rx_12;
                // corruption issue with ppdu_ok and tx_xretry
                input_vec[input_idx++] = R(PPDU_OK_IDX);
                input_vec[input_idx++] = R(TX_XRET_IDX);
                input_vec[input_idx++] = rx_11;
                input_vec[input_idx++] = m1_success_raw;
                input_vec[input_idx++] = m1_packet_raw;
                input_vec[input_idx++] = m3_success_raw;
                input_vec[input_idx++] = m3_packet_raw;
                input_vec[input_idx++] = tx_1_raw;
                input_vec[input_idx++] = tx_11_raw;
                input_vec[input_idx++] = rx_0_raw;
                input_vec[input_idx++] = rx_11_raw;
                input_vec[input_idx++] = m3_success_rate_of_change;
                input_vec[input_idx++] = sum_tx1_tx3_m3_success_rate_of_change;
                input_vec[input_idx++] = tx_mgmt_3;
                input_vec[input_idx++] = is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive;
                input_vec[input_idx++] = is_tx12_or_rx12_active_and_tx1_active;
                // data collection
                input_vec[input_idx++] = clients_per_band;
        }

	float *cur_input = (float *) malloc(INPUT_VEC_LEN * sizeof(float));
	for(int rad_id = 0; rad_id < radio_cnt; rad_id++){
		if(debug_lvl == 1) {
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"input for radio #%d %dg band\n", rad_id, cur_bands[rad_id]);
		}
		for(i = 0; i < INPUT_VEC_LEN; i++){
			cur_input[i] = input_vec[(rad_id *INPUT_VEC_LEN) + i];
			if(debug_lvl == 1) {
				log_message(LOG_LEVEL_AD_LIB_DEBUG,"cur input idx: %d, val %f, input idx %d  val %f\n", i, cur_input[i], (rad_id *INPUT_VEC_LEN) + i, input_vec[(rad_id *INPUT_VEC_LEN) + i]);
				log_message(LOG_LEVEL_AD_LIB_DEBUG,"%f\t", cur_input[i]);
			}
                        if (i < MODEL_VEC_LEN) {
                                cur_input[i] = normalize(cur_bands[rad_id], cur_input[i], i);
                                if(debug_lvl == 1) {
				        log_message(LOG_LEVEL_AD_LIB_DEBUG,"normalized %f\n", cur_input[i]);
			        }
                        }
		}
                // TL=1
                if (debug_lvl == 1 && g_test_level == 1) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "TL=1 active: copying stats for radio #%d", rad_id);
                }
                memcpy(g_last_stats_per_radio[rad_id], &cur_itr[rad_id * CRITICAL_STAT_LEN], sizeof(float) * CRITICAL_STAT_LEN);
                if (debug_lvl == 1 && g_test_level == 1) {
                        for (int j = 0; j < CRITICAL_STAT_LEN; j++) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "g_last_stats_per_radio[%d][%d] = %f", rad_id, j, g_last_stats_per_radio[rad_id][j]);
                        }
                }
                g_last_stats_available[rad_id] = 1;
                if (debug_lvl == 1 && g_test_level == 1) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "g_last_stats_available[%d] = %d", rad_id, g_last_stats_available[rad_id]);
                }

		run_inference(cur_input, rad_id);
	}
	free(input_vec);
	free(cur_input);
	free(diff);
	itr_cnt++;
	for(i = 0; i < total_stats; i++){
		prev_itr[i] = cur_itr[i];
		if(debug_lvl == 1) {
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"prev idx %d: %f\t", i, prev_itr[i]);
		}
	}
}
