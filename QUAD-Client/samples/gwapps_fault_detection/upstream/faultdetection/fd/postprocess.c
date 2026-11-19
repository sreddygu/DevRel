/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>
#include <time.h>
#include <unistd.h>
#include <json-c/json.h>
#include "syslog_processing.h"
#include "postprocess.h"
#include "fault_detection.h"
#include "debugging.h"
#include "cia_services.h"
#include "log_capture.h"

// Static variables moved from fault_detection.c
float g_last_client_change = 0.0f;
float g_last_tx_mgmt_12 = 0.0f;
float g_last_rx_mgmt_12 = 0.0f;

// for tx1_tx11 one interval behind and one interval ahead
static double g_prev1_tx1_by_band[7]     = {0};
static double g_prev1_tx11_by_band[7]    = {0};
static double g_prev2_tx1_by_band[7]     = {0};
static double g_prev2_tx11_by_band[7]    = {0};
static int    g_hist_count_by_band[7]    = {0};
static int    g_tx1tx11_lt025_flag[7]    = {0};
// for rx0_rx11 3-interval period check (same as tx1_tx11)
static double g_prev1_rx0_by_band[7]     = {0};
static double g_prev1_rx11_by_band[7]    = {0};
static double g_prev2_rx0_by_band[7]     = {0};
static double g_prev2_rx11_by_band[7]    = {0};
static int    g_rx0rx11_lt025_flag[7]    = {0};
// for tx1_rx0 3-interval period check (same as tx1_tx11 and rx0_rx11)
static double g_prev1_tx1_rx0_by_band[7] = {0};
static double g_prev1_rx0_tx1_by_band[7] = {0};
static double g_prev2_tx1_rx0_by_band[7] = {0};
static double g_prev2_rx0_tx1_by_band[7] = {0};
static int    g_tx1rx0_lt1_flag[7]       = {0};
// for m1_success_rate_pro and m3_success_rate_pro 3-interval period check
static double g_prev1_m1_success_by_band[7] = {0};
static double g_prev1_m1_packet_by_band[7]  = {0};
static double g_prev1_m3_success_by_band[7] = {0};
static double g_prev1_m3_packet_by_band[7]  = {0};
static double g_prev2_m1_success_by_band[7] = {0};
static double g_prev2_m1_packet_by_band[7]  = {0};
static double g_prev2_m3_success_by_band[7] = {0};
static double g_prev2_m3_packet_by_band[7]  = {0};
static int    g_m1m3_lt_pfzero_flag[7]      = {0};

Thresholds load_thresholds(int cur_band, const char *anomaly_type) {
    const char *radio;
    switch (cur_band) {
        case 2: radio = "2G"; break;
        case 5: radio = "5G"; break;
        case 6: radio = "6G"; break;
        default:
            fprintf(stderr, "Invalid cur_band value: %d\n", cur_band);
            exit(1);
    }

    FILE *file = fopen("/etc/fd/data/training_thresholds.json", "r");
    if (!file) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Failed to open JSON file");
        exit(1);
    }

    fseek(file, 0, SEEK_END);
    long len = ftell(file);
    rewind(file);

    char *data = malloc(len + 1);
    fread(data, 1, len, file);
    data[len] = '\0';
    fclose(file);

    struct json_object *parsed_json = json_tokener_parse(data);
    free(data);

    if (!parsed_json) {
        fprintf(stderr, "Error parsing JSON\n");
        exit(1);
    }

    struct json_object *radio_obj, *anomaly_obj;
    if (!json_object_object_get_ex(parsed_json, radio, &radio_obj) ||
        !json_object_object_get_ex(radio_obj, anomaly_type, &anomaly_obj)) {
        fprintf(stderr, "Missing radio or anomaly type in JSON\n");
        json_object_put(parsed_json);
        exit(1);
    }

    Thresholds t = {
        .beacon_fail_rate_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "beacon_fail_rate")),
        .data_retry_pct_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "data_retry_pct")),
        .tx1_tx11_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "tx1_tx11")),
        .rx0_rx11_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "rx0_rx11")),
        .tx1_rx0_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "tx1_rx0")),
        .tx11_rx11_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "tx11_rx11")),
        .m1_success_rate_pro_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "m1_success_rate_pro")),
        .m3_success_rate_pro_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "m3_success_rate_pro")),
        .m1_m3_rate_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "m1_m3_rate")),
        .is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive")),
        .is_tx12_or_rx12_active_and_tx1_active_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "is_tx12_or_rx12_active_and_tx1_active")),
        .total_clients_threshold = json_object_get_double(json_object_object_get(anomaly_obj, "Control_Stats/Total_Number_of_connected_clients"))
    };

    json_object_put(parsed_json);
    return t;
}


void process_output(float *input, float *output, int cur_band, int rad_id)
{
        char model_label[32] = TEST_LABEL_PASS;

        float model_diffs[MODEL_VEC_LEN];
        time_t current_time;
        int rad = rad_id;

        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Current band during process_output(): %d\n", cur_band);

        for (int i = 0; i < MODEL_VEC_LEN; i++) {
                model_diffs[i] = fabs(output[i] - input[i]);

                if (debug_lvl == 1) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"index: %d -> input: %f, output: %f, abs diff: %f\n", i, input[i], output[i], model_diffs[i]);
                }
        }

        /** rule based variables
		tx1 - assoc resp
		tx11 - auth resp
		rx0 - assoc req
		rx11 - auth req 
		tx_mgmt_12 - deauth from AP
		rx_mgmt_12 - deauth from STA **/
        float beacon_fail_rate = input[14];
        float data_rtry_pct = input[15];
        float tx_mgmt_1 = input[16];
        float tx_mgmt_11 = input[17];
        float tx1_tx11 = input[18];
        float rx0_rx11 = input[19];
        float tx1_rx0 = input[20];
        float tx11_rx11 = input[21];
        float m1_success_rate_pro = input[22];
        float m3_success_rate_pro = input[23];
        float m1_m3_rate = input[24];
        float all_cli_change_regular = input[25];
        float client_change = input[26];
        float tx_mgmt_12 = input[27];
        float rx_mgmt_12 = input[28];
        // ppdu_ok and tx_xretry corrupted
        float ppdu_ok = input[29];
        float tx_xretry = input[30];
        float rx_mgmt_11 = input[31];
        float m1_success_raw = input[32];
        float m1_packet_raw = input[33];
        float m3_success_raw = input[34];
        float m3_packet_raw = input[35];
        float tx_1_raw = input[36];
        float tx_11_raw = input[37];
        float rx_0_raw = input[38];
        float rx_11_raw = input[39];
        float m3_success_rate_of_change = input[40];
        float sum_tx1_tx3_m3_success_rate_of_change = input[41];
        float tx_mgmt_3 = input[42];
        int is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive = input[43];
        int is_tx12_or_rx12_active_and_tx1_active = input[44];
        // client_disconnect notification count
        g_last_tx_mgmt_12 = tx_mgmt_12;
        g_last_rx_mgmt_12 = rx_mgmt_12;
        // data collection
        float clients_per_band = input[45];
        
        // float rx_mgmt_0 = input[13];
        // float rx_mgmt_11 = input[14];
        // !isnan(rx_mgmt_11)

        if(debug_lvl == 1) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Input Values:\n");
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "beacon_fail_rate: %f, data_rtry_pct: %f\n", beacon_fail_rate, data_rtry_pct);
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "tx_mgmt_1: %f, tx_mgmt_11: %f\n", tx_mgmt_1, tx_mgmt_11);
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "tx1_tx11: %f, rx0_rx11: %f, tx1_rx0: %f, tx11_rx11: %f\n", tx1_tx11, rx0_rx11, tx1_rx0, tx11_rx11);
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "m1_success_rate_pro: %f, m3_success_rate_pro: %f, m1_m3_rate: %f\n", m1_success_rate_pro, m3_success_rate_pro, m1_m3_rate);
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "all_cli_change: %f, client_change: %f\n", all_cli_change_regular, client_change);
        }

        // model based variables
        float beacon_fail_rate_model_diffs = model_diffs[0];
        float data_retry_pct_model_diffs = model_diffs[1];
        float tx1_tx11_model_diffs = model_diffs[4];
        float rx0_rx11_model_diffs = model_diffs[5];
        float tx1_rx0_model_diffs = model_diffs[6];
        float tx11_rx11_model_diffs = model_diffs[7];
        float m1_success_rate_pro_model_diffs = model_diffs[8];
        float m3_success_rate_pro_model_diffs = model_diffs[9];
        float m1_m3_rate_model_diffs = model_diffs[10];
        float is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive_model_diffs = model_diffs[11];
        float is_tx12_or_rx12_active_and_tx1_active_model_diffs = model_diffs[12];
        float total_clients_model_diffs = model_diffs[13];

        // Load thresholds
        Thresholds beacon_stuck = load_thresholds(cur_band, TEST_LABEL_BEACON_STUCK);
        Thresholds data_stall = load_thresholds(cur_band, TEST_LABEL_DATA_STALL);
        Thresholds client_disconnect = load_thresholds(cur_band, TEST_LABEL_CLIENT_DISCONNECT);
        Thresholds fail_to_connect = load_thresholds(cur_band, TEST_LABEL_FAIL_TO_CONNECT);

        // check if beacon stuck is an anomaly
        if (beacon_fail_rate_model_diffs >= beacon_stuck.beacon_fail_rate_threshold && beacon_fail_rate > BEACON_FAIL_THRESH && enable_beacon_stuck == 1) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"Beacon Stuck Anomaly Detected on %dG radio\n", cur_band);
                if (debug_lvl == 1) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===beacon_fail_rate_model_diffs: %f >= beacon_fail_rate_model_threshold: %f===\n", beacon_fail_rate_model_diffs, beacon_stuck.beacon_fail_rate_threshold);
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===beacon_fail_rate: %f > beacon_fail_rate_threshold: %f===\n", beacon_fail_rate, BEACON_FAIL_THRESH);
                }
                snprintf(note_value, ANOMALY_VAL_LEN, "Beacon fail rate: %f", beacon_fail_rate);
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"NOTE value:%s\n", note_value);
                if (strcmp(model_label, TEST_LABEL_PASS) == 0) strlcpy(model_label, TEST_LABEL_BEACON_STUCK, sizeof(model_label));
                if (g_test_level == 0) {
                        send_note(rad, cur_band, ANOM_BEACON_STUCK);
                        memset(note_value, '\0', ANOMALY_VAL_LEN);
                }
        } else {
                if (debug_lvl == 1) {
                        if (beacon_fail_rate_model_diffs >= beacon_stuck.beacon_fail_rate_threshold) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===Only Model Anomaly===\n");
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===beacon_fail_rate_model_diffs: %f >= beacon_fail_rate_model_threshold: %f===\n", beacon_fail_rate_model_diffs, beacon_stuck.beacon_fail_rate_threshold);
                        } else {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===beacon_fail_rate_model_diffs: %f < beacon_fail_rate_model_threshold: %f===\n", beacon_fail_rate_model_diffs, beacon_stuck.beacon_fail_rate_threshold);
                        }
                        if (beacon_fail_rate > BEACON_FAIL_THRESH) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===Only Rule Based Anomaly===\n");
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===beacon_fail_rate: %f > beacon_fail_rate_threshold: %f===\n", beacon_fail_rate, BEACON_FAIL_THRESH);
                        } else {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===beacon_fail_rate: %f <= beacon_fail_rate_threshold: %f===\n", beacon_fail_rate, BEACON_FAIL_THRESH);
                        }
                }
        }

        // check if data stall is an anomaly
        if (data_retry_pct_model_diffs >= data_stall.data_retry_pct_threshold && data_rtry_pct > data_stall_threshold && enable_data_stall == 1) {
                if (ppdu_ok >= 0 && tx_xretry >= 0) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Data Stall Anomaly Detected on %dG radio\n", cur_band);
                        if (debug_lvl == 1) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===data_rtry_pct_model_diffs: %f >= data_rtry_pct_model_threshold: %f===\n", data_retry_pct_model_diffs, data_stall.data_retry_pct_threshold);
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===data_rtry_pct: %f > data_rtry_pct_threshold: %f===\n", data_rtry_pct, data_stall_threshold);
                        }
                        snprintf(note_value, ANOMALY_VAL_LEN, "Data retry PCT: %f", data_rtry_pct);
                        if (strcmp(model_label, TEST_LABEL_PASS) == 0) strlcpy(model_label, TEST_LABEL_DATA_STALL, sizeof(model_label));
                        if (g_test_level == 0) {
                                send_note(rad, cur_band, ANOM_DATA_STALL);
                                memset(note_value, '\0', ANOMALY_VAL_LEN);
                        }      
                } else {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===STAT CORRUPTION DETECTED: ppdu_ok rate of change: %f, tx_xretry rate of change: %f===\n", ppdu_ok, tx_xretry);
                }
        } else {
                if (debug_lvl == 1) {
                        if (data_retry_pct_model_diffs >= data_stall.data_retry_pct_threshold) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===Only Model Anomaly===\n");
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===data_rtry_pct_model_diffs: %f >= data_rtry_pct_model_threshold: %f===\n", data_retry_pct_model_diffs, data_stall.data_retry_pct_threshold);
                        } else {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===data_rtry_pct_model_diffs: %f < data_rtry_pct_model_threshold: %f===\n", data_retry_pct_model_diffs, data_stall.data_retry_pct_threshold);
                        }
                        if (data_rtry_pct > data_stall_threshold) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===Only Rule Based Anomaly===\n");
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===data_rtry_pct: %f > data_rtry_pct_threshold: %f===\n", data_rtry_pct, data_stall_threshold);
                        } else {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===data_rtry_pct: %f <= data_rtry_pct_threshold: %f===\n", data_rtry_pct, data_stall_threshold);
                        }
                }
        }

        // check if client disconnect is an anomaly
        int client_disconnect_anomaly_detected = 0;

        if (total_clients_model_diffs >= client_disconnect.total_clients_threshold || is_tx12_or_rx12_active_and_tx1_active_model_diffs >= client_disconnect.is_tx12_or_rx12_active_and_tx1_active_threshold) {
                if (client_disconnect_anomaly_detected == 0 && all_cli_change_regular < 0 && client_change < 0 && enable_client_disconnect == 1) {
                        client_disconnect_anomaly_detected = 1;
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Client Disconnect Anomaly Detected on %dG radio\n", cur_band);
                        if(debug_lvl == 1){
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===total_clients_model_diffs: %f >= total_clients_model_threshold: %f===\n", total_clients_model_diffs, client_disconnect.total_clients_threshold);
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===total_clients change for all radios: %f < 0===\n", all_cli_change_regular);
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"===total_clients change per radio: %f < 0===\n", client_change);
                        }
                        if (strcmp(model_label, TEST_LABEL_PASS) == 0) strlcpy(model_label, TEST_LABEL_CLIENT_DISCONNECT, sizeof(model_label));
                        g_last_client_change = client_change;
                        if (g_test_level == 0) {
                                send_note(rad, cur_band, ANOM_DISCONNECT);
                        }
                } else {
                        if(debug_lvl == 1){
                                if (total_clients_model_diffs >= client_disconnect.total_clients_threshold) {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===Only Model Anomaly===\n");
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===total_clients_model_diffs: %f >= total_clients_model_threshold: %f===\n", total_clients_model_diffs, client_disconnect.total_clients_threshold);
                                } else {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===total_clients_model_diffs: %f < total_clients_model_threshold: %f===\n", total_clients_model_diffs, client_disconnect.total_clients_threshold);
                                }
                                if(all_cli_change_regular < 0) {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===Only Rule Based Anomaly===\n");
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===total_clients change for all radios: %f < 0===\n", all_cli_change_regular);
                                } else {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===total_clients change for all radios: %f >= 0===\n", all_cli_change_regular);
                                }
                                if(client_change < 0) {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===Only Rule Based Anomaly===\n");
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===total_clients change per radio: %f < 0===\n", client_change);
                                } else {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===total_clients change per radio: %f >= 0===\n", client_change);
                                }
                        }
                }

                // client disconnect within interval
                if(client_disconnect_anomaly_detected == 0 && all_cli_change_regular == 0 && is_tx12_or_rx12_active_and_tx1_active == 1 && enable_client_disconnect == 1){
                        client_disconnect_anomaly_detected = 1;
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Disconnect Anomaly Detected on %dG radio (tx_mgmt_12 > 0 || rx_mgmt_12 > 0) && (sum_tx1_tx3_m3_success_rate_of_change > 0)\n", cur_band);
                        if (tx_mgmt_12 > 0) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "tx_mgmt_12: %f sum_tx1_tx3_m3_success_rate_of_change: %f\n", tx_mgmt_12, sum_tx1_tx3_m3_success_rate_of_change);
                        }
                        if (rx_mgmt_12 > 0) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "rx_mgmt_12: %f sum_tx1_tx3_m3_success_rate_of_change: %f\n", rx_mgmt_12, sum_tx1_tx3_m3_success_rate_of_change);
                        }
                        if (strcmp(model_label, TEST_LABEL_PASS) == 0) strlcpy(model_label, TEST_LABEL_CLIENT_DISCONNECT, sizeof(model_label));
                        g_last_client_change = client_change;
                        if (g_test_level == 0) {
                                send_note(rad, cur_band, ANOM_DISCONNECT);
                        }   
                }
        }

        // check if fail to connect is an anomaly
        int fail_to_connect_anomaly_detected = 0;

        if ((tx1_tx11_model_diffs >= fail_to_connect.tx1_tx11_threshold || rx0_rx11_model_diffs >= fail_to_connect.rx0_rx11_threshold || tx1_rx0_model_diffs >= fail_to_connect.tx1_rx0_threshold ||
                m1_success_rate_pro_model_diffs >= fail_to_connect.m1_success_rate_pro_threshold || m3_success_rate_pro_model_diffs >= fail_to_connect.m3_success_rate_pro_threshold ||
                m1_m3_rate_model_diffs >= fail_to_connect.m1_m3_rate_threshold || is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive_model_diffs >= fail_to_connect.is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive_threshold) &&
                all_cli_change_regular == 0 && enable_fail_to_connect == 1) {

                const int b = cur_band; // 2, 5, or 6

                if (debug_lvl == 1) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===Model Detects Fail to Connect Anomaly===\n");
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===tx1_tx11_model_diffs:%f tx1_tx11_threshold: %f===\n", tx1_tx11_model_diffs, fail_to_connect.tx1_tx11_threshold);
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===rx0_rx11_model_diffs:%f rx0_rx11_threshold: %f===\n", rx0_rx11_model_diffs, fail_to_connect.rx0_rx11_threshold);
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===tx1_rx0_model_diffs:%f tx1_rx0_threshold: %f===\n", tx1_rx0_model_diffs, fail_to_connect.tx1_rx0_threshold);
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===m1_m3_rate_model_diffs:%f m1_m3_rate_threshold: %f===\n", m1_m3_rate_model_diffs, fail_to_connect.m1_m3_rate_threshold);
                }

                // fail to connect within interval
                if(fail_to_connect_anomaly_detected == 0 && all_cli_change_regular == 0 && is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive == 1 && enable_fail_to_connect == 1){
                        fail_to_connect_anomaly_detected = 1;
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Fail to Connect Anomaly Detected on %dG radio (tx_mgmt_12 > 0 || rx_mgmt_12 > 0)\n", cur_band);
                        if (tx_mgmt_12 > 0) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "tx_mgmt_12: %f\n", tx_mgmt_12);
                        }
                        if (rx_mgmt_12 > 0) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "rx_mgmt_12: %f\n", rx_mgmt_12);
                        }
                        if (strcmp(model_label, TEST_LABEL_PASS) == 0) strlcpy(model_label, TEST_LABEL_FAIL_TO_CONNECT, sizeof(model_label));
                        if (g_test_level == 0) {
                                send_note(rad, cur_band, ANOM_FAIL_CONNECT);
                        }      
                }

                // m1_m3_rate
                if(fail_to_connect_anomaly_detected == 0) {
                        if(m1_m3_rate != 1 && m1_m3_rate != 0) {
                                fail_to_connect_anomaly_detected = 1;
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"Fail to Connect Anomaly Detected on %dG radio 1_m3_rate != 1 && m1_m3_rate != 0\n", cur_band);
                                if(debug_lvl == 1){
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===m1_m3_rate: %f===\n", m1_m3_rate);
                                }
                                if (strcmp(model_label, TEST_LABEL_PASS) == 0) strlcpy(model_label, TEST_LABEL_FAIL_TO_CONNECT, sizeof(model_label));
                                if (g_test_level == 0) {
                                        send_note(rad, cur_band, ANOM_FAIL_CONNECT);
                                } 
                        } else {
                                if(debug_lvl == 1){
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"===m1_m3_rate: %f===\n", m1_m3_rate);
                                }
                        }
                }

                // m1_success_rate_pro == 1, m3_success_rate_pro == 1 on 3-interval period
                if (all_cli_change_regular == 0 && fail_to_connect_anomaly_detected == 0 && g_m1m3_lt_pfzero_flag[b] == 1 && g_hist_count_by_band[b] >= 2 && enable_fail_to_connect == 1) {

                        const double cur_m1_success  = (double)m1_success_raw;
                        const double cur_m1_packet   = (double)m1_packet_raw;
                        const double cur_m3_success  = (double)m3_success_raw;
                        const double cur_m3_packet   = (double)m3_packet_raw;
                        const double prev2_m1_success = g_prev2_m1_success_by_band[b];
                        const double prev2_m1_packet  = g_prev2_m1_packet_by_band[b];
                        const double prev2_m3_success = g_prev2_m3_success_by_band[b];
                        const double prev2_m3_packet  = g_prev2_m3_packet_by_band[b];

                        const int have_vals = (!isnan(cur_m1_success) && !isnan(cur_m1_packet) && 
                                        !isnan(cur_m3_success) && !isnan(cur_m3_packet) &&
                                        !isnan(prev2_m1_success) && !isnan(prev2_m1_packet) &&
                                        !isnan(prev2_m3_success) && !isnan(prev2_m3_packet));

                        if (have_vals) {
                                const double delta_m1_success = cur_m1_success - prev2_m1_success;
                                const double delta_m1_packet  = cur_m1_packet  - prev2_m1_packet;
                                const double delta_m3_success = cur_m3_success - prev2_m3_success;
                                const double delta_m3_packet  = cur_m3_packet  - prev2_m3_packet;

                                int m1_anomaly = 0;
                                int m3_anomaly = 0;

                                if (delta_m1_packet != 0.0 && !isnan(delta_m1_success) && !isnan(delta_m1_packet)) {
                                        const double delta_m1_rate = delta_m1_success / delta_m1_packet;

                                        if (debug_lvl == 1) {
                                                log_message(LOG_LEVEL_AD_LIB_DEBUG,
                                                        "[resolve-pending-m1m3] band=%dG, "
                                                        "cur_m1_success_raw=%.6f, prev2_m1_success_raw=%.6f, d_m1_success_raw=%.6f; "
                                                        "cur_m1_packet_raw=%.6f, prev2_m1_packet_raw=%.6f, d_m1_packet_raw=%.6f; "
                                                        "delta_m1_rate_raw=%.6f",
                                                        cur_band, cur_m1_success, prev2_m1_success, delta_m1_success,
                                                        cur_m1_packet, prev2_m1_packet, delta_m1_packet, delta_m1_rate);
                                        }

                                        if (delta_m1_rate < PFZERO) {
                                                m1_anomaly = 1;
                                        }
                                } else if (debug_lvl == 1) {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[resolve-pending-m1m3] Skipped M1: delta_m1_packet=%.6f (must != 0)", delta_m1_packet);
                                }

                                if (delta_m3_packet != 0.0 && !isnan(delta_m3_success) && !isnan(delta_m3_packet)) {
                                        const double delta_m3_rate = delta_m3_success / delta_m3_packet;

                                        if (debug_lvl == 1) {
                                                log_message(LOG_LEVEL_AD_LIB_DEBUG,
                                                        "[resolve-pending-m1m3] band=%dG, "
                                                        "cur_m3_success_raw=%.6f, prev2_m3_success_raw=%.6f, d_m3_success_raw=%.6f; "
                                                        "cur_m3_packet_raw=%.6f, prev2_m3_packet_raw=%.6f, d_m3_packet_raw=%.6f; "
                                                        "delta_m3_rate_raw=%.6f",
                                                        cur_band, cur_m3_success, prev2_m3_success, delta_m3_success,
                                                        cur_m3_packet, prev2_m3_packet, delta_m3_packet, delta_m3_rate);
                                        }

                                        if (delta_m3_rate < PFZERO) {
                                                m3_anomaly = 1;
                                        }
                                } else if (debug_lvl == 1) {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[resolve-pending-m1m3] Skipped M3: delta_m3_packet=%.6f (must != 0)", delta_m3_packet);
                                }

                                if (m1_anomaly || m3_anomaly) {
                                        fail_to_connect_anomaly_detected = 1;
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Fail to Connect Anomaly Detected on %dG radio: m1_success_rate or m3_success_rate < PFZERO on two-interval delta",
                                                cur_band);
                                        if (debug_lvl == 1) {
                                                if (m1_anomaly) {
                                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "===M1 anomaly: delta_m1_success: %f, delta_m1_packet: %f===", delta_m1_success, delta_m1_packet);
                                                }
                                                if (m3_anomaly) {
                                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "===M3 anomaly: delta_m3_success: %f, delta_m3_packet: %f===", delta_m3_success, delta_m3_packet);
                                                }
                                        }
                                        if (strcmp(model_label, TEST_LABEL_PASS) == 0) {
                                                strlcpy(model_label, TEST_LABEL_FAIL_TO_CONNECT, sizeof(model_label));
                                        }
                                        if (g_test_level == 0) {
                                                send_note(rad, cur_band, ANOM_FAIL_CONNECT);
                                        }
                                }
                        } else if (debug_lvl == 1) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[resolve-pending-m1m3] Skipped: NaN m1/m3 values in current or history");
                        }
                }

                g_m1m3_lt_pfzero_flag[b] = 0;

                if (all_cli_change_regular == 0 && fail_to_connect_anomaly_detected == 0 && (m1_success_rate_pro == 1 || m3_success_rate_pro == 1)) {
                        g_m1m3_lt_pfzero_flag[b] = 1;
                } else {
                        g_m1m3_lt_pfzero_flag[b] = 0;
                }
                g_prev2_m1_success_by_band[b] = g_prev1_m1_success_by_band[b];
                g_prev2_m1_packet_by_band[b]  = g_prev1_m1_packet_by_band[b];
                g_prev2_m3_success_by_band[b] = g_prev1_m3_success_by_band[b];
                g_prev2_m3_packet_by_band[b]  = g_prev1_m3_packet_by_band[b];
                g_prev1_m1_success_by_band[b] = (double)m1_success_raw;
                g_prev1_m1_packet_by_band[b]  = (double)m1_packet_raw;
                g_prev1_m3_success_by_band[b] = (double)m3_success_raw;
                g_prev1_m3_packet_by_band[b]  = (double)m3_packet_raw;

                // tx1_tx11 on 3-interval period
                if (fail_to_connect_anomaly_detected == 0 && g_tx1tx11_lt025_flag[b] == 1 && g_hist_count_by_band[b] >= 2) {

                        const double cur_tx1   = (double)tx_1_raw;   
                        const double cur_tx11  = (double)tx_11_raw;  
                        const double prev2_tx1 = g_prev2_tx1_by_band[b];    
                        const double prev2_tx11= g_prev2_tx11_by_band[b];

                        const int have_vals = (!isnan(cur_tx1) && !isnan(cur_tx11) && !isnan(prev2_tx1) && !isnan(prev2_tx11));

                        if (have_vals) {
                                const double delta_tx1  = cur_tx1  - prev2_tx1;   
                                const double delta_tx11 = cur_tx11 - prev2_tx11;  

                                if (delta_tx11 != 0.0 && !isnan(delta_tx1) && !isnan(delta_tx11)) {
                                        const double delta_ratio = delta_tx1 / delta_tx11;

                                        if (debug_lvl == 1) {
                                                log_message(LOG_LEVEL_AD_LIB_DEBUG,
                                                        "[resolve-pending] band=%dG, "
                                                        "cur_tx1_raw=%.6f, prev2_tx1_raw=%.6f, d_tx1_raw=%.6f; "
                                                        "cur_tx11_raw=%.6f, prev2_tx11_raw=%.6f, d_tx11_raw=%.6f; "
                                                        "delta_ratio_raw=%.6f",
                                                        cur_band, cur_tx1, prev2_tx1, delta_tx1,
                                                        cur_tx11, prev2_tx11, delta_tx11, delta_ratio);
                                        }

                                        if (delta_ratio < FDOT25) {
                                                fail_to_connect_anomaly_detected = 1;
                                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Fail to Connect Anomaly Detected on %dG radio: tx1_tx11<FDOT25 on two-interval delta ratio < 0.25",
                                                        cur_band);
                                                if (debug_lvl == 1) {
                                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "===delta_tx1: %f, delta_tx11: %f, delta_ratio: %f===", delta_tx1, delta_tx11, delta_ratio);
                                                }
                                                if (strcmp(model_label, TEST_LABEL_PASS) == 0) {
                                                        strlcpy(model_label, TEST_LABEL_FAIL_TO_CONNECT, sizeof(model_label));
                                                }
                                                if (g_test_level == 0) {
                                                        send_note(rad, cur_band, ANOM_FAIL_CONNECT);
                                                }
                                        }
                                } else if (debug_lvl == 1) {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[resolve-pending] Skipped: delta_tx11=%.6f (must != 0)", delta_tx11);
                                }
                        } else if (debug_lvl == 1) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[resolve-pending] Skipped: NaN tx1_tx11 in current or history");
                        }
                }

                g_tx1tx11_lt025_flag[b] = 0;

                if (fail_to_connect_anomaly_detected == 0 && !isnan(tx1_tx11) && tx1_tx11 < FDOT25) {
                        g_tx1tx11_lt025_flag[b] = 1;
                } else {
                        g_tx1tx11_lt025_flag[b] = 0;
                }
                g_prev2_tx1_by_band[b]   = g_prev1_tx1_by_band[b];
                g_prev2_tx11_by_band[b]  = g_prev1_tx11_by_band[b];
                g_prev1_tx1_by_band[b]   = (double)tx_1_raw;
                g_prev1_tx11_by_band[b]  = (double)tx_11_raw;
                if (g_hist_count_by_band[b] < 2) {
                        g_hist_count_by_band[b]++;
                }

                // rx0_rx11 on 3-interval period
                if (fail_to_connect_anomaly_detected == 0 && g_rx0rx11_lt025_flag[b] == 1 && g_hist_count_by_band[b] >= 2) {

                        const double cur_rx0   = (double)rx_0_raw;   
                        const double cur_rx11  = (double)rx_11_raw;  
                        const double prev2_rx0 = g_prev2_rx0_by_band[b];    
                        const double prev2_rx11= g_prev2_rx11_by_band[b];

                        const int have_vals = (!isnan(cur_rx0) && !isnan(cur_rx11) && !isnan(prev2_rx0) && !isnan(prev2_rx11));

                        if (have_vals) {
                                const double delta_rx0  = cur_rx0  - prev2_rx0;   
                                const double delta_rx11 = cur_rx11 - prev2_rx11;  

                                if (delta_rx11 != 0.0 && !isnan(delta_rx0) && !isnan(delta_rx11)) {
                                        const double delta_ratio = delta_rx0 / delta_rx11;

                                        if (debug_lvl == 1) {
                                                log_message(LOG_LEVEL_AD_LIB_DEBUG,
                                                        "[resolve-pending-rx0rx11] band=%dG, "
                                                        "cur_rx0_raw=%.6f, prev2_rx0_raw=%.6f, d_rx0_raw=%.6f; "
                                                        "cur_rx11_raw=%.6f, prev2_rx11_raw=%.6f, d_rx11_raw=%.6f; "
                                                        "delta_ratio_raw=%.6f",
                                                        cur_band, cur_rx0, prev2_rx0, delta_rx0,
                                                        cur_rx11, prev2_rx11, delta_rx11, delta_ratio);
                                        }

                                        if (delta_ratio < FDOT25) {
                                                fail_to_connect_anomaly_detected = 1;
                                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Fail to Connect Anomaly Detected on %dG radio: rx0_rx11<FDOT25 on two-interval delta ratio < 0.25",
                                                        cur_band);
                                                if (debug_lvl == 1) {
                                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "===delta_rx0: %f, delta_rx11: %f, delta_ratio: %f===", delta_rx0, delta_rx11, delta_ratio);
                                                }
                                                if (strcmp(model_label, TEST_LABEL_PASS) == 0) {
                                                        strlcpy(model_label, TEST_LABEL_FAIL_TO_CONNECT, sizeof(model_label));
                                                }
                                                if (g_test_level == 0) {
                                                        send_note(rad, cur_band, ANOM_FAIL_CONNECT);
                                                }
                                        }
                                } else if (debug_lvl == 1) {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[resolve-pending-rx0rx11] Skipped: delta_rx11=%.6f (must != 0)", delta_rx11);
                                }
                        } else if (debug_lvl == 1) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[resolve-pending-rx0rx11] Skipped: NaN rx0_rx11 in current or history");
                        }
                }

                g_rx0rx11_lt025_flag[b] = 0;

                if (fail_to_connect_anomaly_detected == 0 && !isnan(rx0_rx11) && rx0_rx11 < FDOT25) {
                        g_rx0rx11_lt025_flag[b] = 1;
                } else {
                        g_rx0rx11_lt025_flag[b] = 0;
                }
                g_prev2_rx0_by_band[b]   = g_prev1_rx0_by_band[b];
                g_prev2_rx11_by_band[b]  = g_prev1_rx11_by_band[b];
                g_prev1_rx0_by_band[b]   = (double)rx_0_raw;
                g_prev1_rx11_by_band[b]  = (double)rx_11_raw;
                
                // tx1_rx0 on 3-interval period
                if (fail_to_connect_anomaly_detected == 0 && g_tx1rx0_lt1_flag[b] == 1 && g_hist_count_by_band[b] >= 2) {

                        const double cur_tx1_for_rx0   = (double)tx_1_raw;   
                        const double cur_rx0_for_tx1   = (double)rx_0_raw;  
                        const double prev2_tx1_for_rx0 = g_prev2_tx1_rx0_by_band[b];    
                        const double prev2_rx0_for_tx1 = g_prev2_rx0_tx1_by_band[b];

                        const int have_vals = (!isnan(cur_tx1_for_rx0) && !isnan(cur_rx0_for_tx1) && !isnan(prev2_tx1_for_rx0) && !isnan(prev2_rx0_for_tx1));

                        if (have_vals) {
                                const double delta_tx1_for_rx0 = cur_tx1_for_rx0 - prev2_tx1_for_rx0;   
                                const double delta_rx0_for_tx1 = cur_rx0_for_tx1 - prev2_rx0_for_tx1;  

                                if (delta_rx0_for_tx1 != 0.0 && !isnan(delta_tx1_for_rx0) && !isnan(delta_rx0_for_tx1)) {
                                        const double delta_ratio = delta_tx1_for_rx0 / delta_rx0_for_tx1;

                                        if (debug_lvl == 1) {
                                                log_message(LOG_LEVEL_AD_LIB_DEBUG,
                                                        "[resolve-pending-tx1rx0] band=%dG, "
                                                        "cur_tx1_raw=%.6f, prev2_tx1_raw=%.6f, d_tx1_raw=%.6f; "
                                                        "cur_rx0_raw=%.6f, prev2_rx0_raw=%.6f, d_rx0_raw=%.6f; "
                                                        "delta_ratio_raw=%.6f",
                                                        cur_band, cur_tx1_for_rx0, prev2_tx1_for_rx0, delta_tx1_for_rx0,
                                                        cur_rx0_for_tx1, prev2_rx0_for_tx1, delta_rx0_for_tx1, delta_ratio);
                                        }

                                        if (delta_ratio < 1.0) {
                                                fail_to_connect_anomaly_detected = 1;
                                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Fail to Connect Anomaly Detected on %dG radio: tx1_rx0<FONE on two-interval delta ratio < 1.0",
                                                        cur_band);
                                                if (debug_lvl == 1) {
                                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "===delta_tx1: %f, delta_rx0: %f, delta_ratio: %f===", delta_tx1_for_rx0, delta_rx0_for_tx1, delta_ratio);
                                                }
                                                if (strcmp(model_label, TEST_LABEL_PASS) == 0) {
                                                        strlcpy(model_label, TEST_LABEL_FAIL_TO_CONNECT, sizeof(model_label));
                                                }
                                                if (g_test_level == 0) {
                                                        send_note(rad, cur_band, ANOM_FAIL_CONNECT);
                                                }
                                        }
                                } else if (debug_lvl == 1) {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[resolve-pending-tx1rx0] Skipped: delta_rx0=%.6f (must != 0)", delta_rx0_for_tx1);
                                }
                        } else if (debug_lvl == 1) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[resolve-pending-tx1rx0] Skipped: NaN tx1_rx0 in current or history");
                        }
                }

                g_tx1rx0_lt1_flag[b] = 0;

                if (fail_to_connect_anomaly_detected == 0 && !isnan(tx1_rx0) && tx1_rx0 < FONE) {
                        g_tx1rx0_lt1_flag[b] = 1;
                } else {
                        g_tx1rx0_lt1_flag[b] = 0;
                }
                g_prev2_tx1_rx0_by_band[b] = g_prev1_tx1_rx0_by_band[b];
                g_prev2_rx0_tx1_by_band[b] = g_prev1_rx0_tx1_by_band[b];
                g_prev1_tx1_rx0_by_band[b] = (double)tx_1_raw;
                g_prev1_rx0_tx1_by_band[b] = (double)rx_0_raw;

        }

        // For usb, check and reset syslog if time has been exceeded
        if (save_logs_to_usb == 1) {
                check_and_reset_syslog_if_needed();
        }
        

        current_time = time(NULL);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Time: %s\n", asctime(localtime(&current_time)));

        if (g_test_level == 1) {
                if (debug_lvl == 1) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[TL=1] Sending TL1 sample for radio #%d, band %dG, label: %s", rad_id, cur_band, model_label);
                }
                
                // Calculate disconnect count
                int disc = (int)(clients_per_band * inf_inter);
                
                send_tl1_sample(rad_id, cur_band, model_label, (float)disc);
        }
        
        if (g_test_level == 2 && g_tl2_pending[rad_id]) {
                char expected[32]; strlcpy(expected, g_tl2_expected_label[rad_id], sizeof(expected));
                for (char *p = expected; *p; ++p) *p = (char)tolower((unsigned char)*p);

                char observed[32]; strlcpy(observed, model_label, sizeof(observed));
                for (char *p = observed; *p; ++p) *p = (char)tolower((unsigned char)*p);

                const int match = (strcmp(expected, observed) == 0);
                
                send_tl2_result_for(rad_id, g_tl2_message_id[rad_id], match ? TEST_LABEL_PASS : "fail", observed);

                g_tl2_message_id[rad_id][0] = '\0';
                g_tl2_expected_label[rad_id][0] = '\0';
                g_tl2_pending[rad_id] = 0;
        }


}
