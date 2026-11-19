/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <sys/time.h>
#include <math.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <ctype.h>
#include "fault_detection.h"
#include "transport_client.h"
#include <sys/socket.h>
#include <arpa/inet.h>
#include "license_verify.h"
#include "transport_client.h"/*
 *this header file would be available as part of staging_dir/usr/include/winai
 * Please ensure winai_sdk is compiled prior to it.
 */
#include "nwaios_lib.h"
#include "cia_services.h"
#include "syslog_processing.h"
#include "log_capture.h"
#include "notification_processing.h"
#include "debugging.h"
#include "model_inferencing.h"
#include "preprocess.h"
#include "postprocess.h"
// cloud imports
#include <dirent.h>
#include <regex.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <fcntl.h>
#include <errno.h>
#include <libgen.h>
// normalization
#include <json-c/json.h>
#include <regex.h>
#include <stdarg.h>
#include <limits.h>
#include "peer_stats.h"

// Define stat_name array (declared as extern in fault_detection.h)
const char * stat_name[CRITICAL_STAT_LEN] = {"Rx_Management", "Tx_Management", "hwq_id_0_type_0", "hwq_id_0_type_1", "hwq_id_0_type_2", "hwq_id_0_type_3", 
				"hwq_id_0_type_4", "hwq_id_0_type_5", "hwq_id_0_type_6", "hwq_id_0_type_7", "hwq_id_0_type_8", "hwq_id_0_type_9", "hwq_id_0_type_10",
				"hwq_id_0_type_11", "hwq_id_0_type_12", "hwq_id_4_type_0", "hwq_id_4_type_1", "hwq_id_4_type_2", "hwq_id_4_type_3", 
				"hwq_id_4_type_4", "hwq_id_4_type_5", "hwq_id_4_type_6", "hwq_id_4_type_7", "hwq_id_4_type_8", "hwq_id_4_type_9", 
				"hwq_id_4_type_10", "hwq_id_4_type_11", "hwq_id_4_type_12", "ppdu_ok", "tx_xretry", "fw_rx_mgmt_subtype_type_0",
				"fw_rx_mgmt_subtype_type_2", "fw_rx_mgmt_subtype_type_4", "fw_rx_mgmt_subtype_type_11", "fw_rx_mgmt_subtype_type_12",
				"fw_tx_mgmt_subtype_type_1", "fw_tx_mgmt_subtype_type_3", "fw_tx_mgmt_subtype_type_5", "fw_tx_mgmt_subtype_type_10",
				"fw_tx_mgmt_subtype_type_11", "fw_tx_mgmt_subtype_type_12", "m1_packets", "m3_packets", "m1_success", "m3_success", "total clients",
				/* indices 46-49: RSSI stats already populated by fd_lib */
				"rssi_mgmt", "rssi_data", "rssi_comb", "rssi_in_dbm",
				/* indices 50-53: new CCA counters */
				"rx_clear", "tx_frame", "my_rx_frame", "rx_frame"};

// Local defines not in header
#define FILE_PATH_LEN 1024
#define MODEL_PATH_LEN 256
// cloud
#define R(idx)   (diff[(diff_idx) + (idx)])

// char note_mac[NOTE_MAC_LEN];
static char note_value_storage[ANOMALY_VAL_LEN];
char *note_value = note_value_storage;
char note_message[NOTE_LEN];
// char note_link[NOTE_MAC_LEN];
// char note_reason[CMD_LEN];
char log_folder[CMD_LEN];
int radios_count;
char radios[MAX_RADIOS][VAP_RADIO_LEN_MAX];
char radio_macs[MAX_RADIOS][MAC_ADDRESS_LEN_IN_CHARS];
char reference_wifistat_path_2g[CMD_LEN] = {0};
char reference_wifistat_path_5g[CMD_LEN] = {0};
char reference_wifistat_path_6g[CMD_LEN] = {0};
int critical_stat[] = {3, 1, 48, 8, 37};
int anomaly_stat[] = {1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 17, 18, 19, 21, 37, 48};
float pct_2g = 0.4;
float pct_5g = 1.7;
float pct_6g = 0.87;
int buffer_len = 0;
int cur_cir_idx= 0;
int stats_count = 0;
float *cir_buffer = NULL;
float *input_vec = NULL;
float *prev_itr = NULL;
float *cur_itr = NULL;
time_t time_prev, time_cur;
int stats_len = 0;
int *bands;
int debug_lvl = 0;

int save_logs_to_usb = 0;
// float mse_2g = MSE_2G;
// float mse_5g = MSE_5G;
// float mse_6g = MSE_6G;
int total_clients = 0;
int interval_seconds = 0;
float *prev_m1_rate = NULL;
float *prev_m3_rate = NULL;
float *prev_m1_m3_rate = NULL;
int verify_license(uint32_t fid_to_check);
int get_wifi_stats_native(char * stats, int stats_len, char *bands, int radios_cnt, int lvl);
int start_pkt_log_native();
void timestamp_native();
void send_notification_native(int Radio_id, int anomaly_cnt, int anomaly_hist_cnt, int band, int stamp, int type, int pkt_log);
// Forward declarations
int save_buffer(float *buf, int radio_id, const char *notif_path);
void send_note(int rad_id, int band, int type);

int inf_inter = 10;
float data_stall_threshold = DATA_STALL_THRESHOLD_DEFAULT;
int anomaly_detected = 0;
int buffer_history = DEFAULT_BUFFER;
int enable_pkt = 0;
int enable_peer_stats = 0;
int enable_data_stall = 1;
int enable_beacon_stuck = 1;
int enable_client_disconnect = 1;
int enable_fail_to_connect = 1;
int MAX_PEERS = 512;
char log_dir[MAX_LEN] = "/tmp/";
int radio_count = 0;
int anomaly_count = 0;
int max_anomaly_count = DEFAULT_MAX_ANOMALY_FOLDERS;
int effective_max_anomaly_count = DEFAULT_MAX_ANOMALY_FOLDERS;

int current_anomaly_band = 0;
int *anomaly_itr = NULL;
int itr_cnt = 0;
int ath_build = 0;
int *anomaly_history = NULL;
struct timeval stamp_seconds;
int stamp;
int cur_bands[MAX_RADIOS];
int prev_cli_count = 0;
// TL=1
int g_test_level = 0;
char g_test_label[64] = {0};
char g_test_name[64]  = {0};
float g_last_stats_per_radio[MAX_RADIOS][CRITICAL_STAT_LEN];
int   g_last_stats_available[MAX_RADIOS] = {0};
// TL=2
char g_tl2_expected_label[MAX_RADIOS][32];
char g_tl2_message_id[MAX_RADIOS][128];
int  g_tl2_pending[MAX_RADIOS] = {0};
// per-band previous state (to avoid cross-band diffs) ---
float *g_prev_itr_by_band[7] = { NULL };  // index by band number (2,5,6)
int    g_prev_cli_by_band[7] = { 0 };     // per-band total_clients baseline
int g_tl2_cycle_no = -1;                 // last known cycle number, if provided
int g_tl2_seen_first_by_band[7] = {0};   // per-band "first-sample seen" for current cycle
int g_broadcast_test_level = 1;          // Broadcast test level on startup if level is 1 or 2

// debuggability declarations moved to debugging.h/c

// debuggability declarations moved to debugging.h/c
/* Historical state variables moved to postprocess.c */

time_t g_last_send_note_time = 0;
int active_freqs[MAX_RADIO_FREQS];
char cur_sys_path[PATH_MAX];
int sys_log_avail = 0;
/** To be moved to the library **/
static int ath_radios_count;
char stat_folder_prefix[] = "/sys/kernel/debug/ath12k/";
char suffix_echo[] = "/mac0/htt_stats_type";
char suffix_read[] = "/mac0/htt_stats";
char suffix_host_read[] = "/mac0/dump_mgmt_stats";

int get_radio_center_freq(const char *folder_name) {
    char echo_path[FILE_PATH_LEN];
    char read_path[FILE_PATH_LEN];
    FILE *echo_file = NULL;
    FILE *read_file = NULL;
    char stat_buf[CMD_LEN];
    int freq_val = 0;

    log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] Called for folder: %s\n", folder_name);

    snprintf(echo_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_echo);
    snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_read);

    log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] echo_path: %s\n", echo_path);
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] read_path: %s\n", read_path);

    char echo_cmd[CMD_LEN];
    snprintf(echo_cmd, sizeof(echo_cmd), "echo 37 > %s", echo_path);
    echo_file = popen(echo_cmd, "w");
    if (echo_file == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] Failed to popen echo command\n");
        return 0;
    }
    pclose(echo_file);

    // Add small delay allow it to populate.
    usleep(100);

    read_file = fopen(read_path, "r");
    if(read_file == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] Failed to open read_path: %s\n", read_path);
        return 0;
    }
    
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] Searching for 'operating center freq' in file\n");
    while(fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
        if(strstr(stat_buf, "operating center freq")){
            char *center_freq = strstr(stat_buf,"=");
            freq_val = atoi(&center_freq[2]);
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] Found center freq line: %s\n", stat_buf);
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] Parsed freq_val: %d\n", freq_val);
            break;
        }
    }
    fclose(read_file);
    
    if (freq_val == 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] WARNING: freq_val is 0 for folder %s\n", folder_name);
    }
    
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "[get_radio_center_freq] Returning freq_val: %d\n", freq_val);
    return freq_val;
}

void init_aps_and_radios() {

    char command[TOP_CMD_LEN]={};
    char top_output[TOP_OUTPUT_LEN]= {};
    snprintf(command,TOP_CMD_LEN-1,"ifconfig | grep -e wifi");
    FILE *fp = popen(command, "r");
    if(!fp){
      log_message(LOG_LEVEL_AD_LIB_DEBUG,"popen failed");
      return;
    }
    int j=0;
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Initialize APs : Counting Radios \n");
    while(fgets(top_output, sizeof(top_output)-1, fp)) {
        char mac[MAC_ADDRESS_LEN_IN_CHARS] = {0};

        if (0 != strstr(top_output, "wifi")) {
            int x =0;
            sscanf(top_output, "%s Link %*s  HWaddr %17s", radios[j], mac);
            for(x =0; x <MAC_ADDRESS_LEN_IN_CHARS; x++) {
                if(mac[x] == '-')  mac[x] = ':';
            }
            log_message(LOG_LEVEL_AD_LIB_DEBUG," [%d] %s >>> %s\n", j, radios[j], mac);
            strlcpy(radio_macs[j], mac, sizeof(radio_macs[j]));
            j++;
        }
    }
    radios_count = j;
    if(fp) pclose(fp);
}

void parse_config(char *buffer){
    char *val = strchr(buffer, '=');
    if (!val) return;
    val++;
    // Skip leading whitespace
    while (*val == ' ' || *val == '\t') val++;
    // Remove trailing whitespace, newlines, and carriage returns
    size_t vlen = strlen(val);
    while (vlen > 0 && (val[vlen-1] == '\n' || val[vlen-1] == '\r' || 
                        val[vlen-1] == ' ' || val[vlen-1] == '\t')) {
        val[--vlen] = '\0';
    }
    // Skip if empty value after trimming
    if (vlen == 0) return;

    if(strstr(buffer, "interval")){
        inf_inter = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"inference interval %d\n", inf_inter);
    } else if(strstr(buffer, "buffer_capacity")) {
        buffer_history = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"buffer_history %d\n", buffer_history);
    } else if(strstr(buffer, "log_path")) {
        strlcpy(log_dir, val, sizeof(log_dir));
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"log_path %s\n", log_dir);
    } else if(strstr(buffer, "save_logs_to_usb")) {
        save_logs_to_usb = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"save_logs_to_usb %d\n", save_logs_to_usb);
    } else if(strstr(buffer, "max_anomaly_folders")) {
        max_anomaly_count = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"max_anomaly_folders %d\n", max_anomaly_count);
    } else if(strstr(buffer, "debug")) {
        debug_lvl = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"debug %d\n", debug_lvl);
    } else if(strstr(buffer, "enable_pkt_log")) {
        enable_pkt = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"enable_pkt %d\n", enable_pkt);
    } else if (strstr(buffer, "enable_peer_stats")) {
        enable_peer_stats = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"enable_peer_stats %d\n", enable_peer_stats);
    } else if (strstr(buffer, "max_peer_count")) {
        MAX_PEERS = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"max_peer_count %d\n", MAX_PEERS);
    // test app
    } else if (strstr(buffer, "TEST_LEVEL")) {
        g_test_level = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"TEST_LEVEL %d\n", g_test_level);
    } else if (strstr(buffer, "TEST_LABEL")) {
        strlcpy(g_test_label, val, sizeof(g_test_label));
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"TEST_LABEL %s\n", g_test_label);
    } else if (strstr(buffer, "TEST_NAME")) {
        strlcpy(g_test_name, val, sizeof(g_test_name));
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"TEST_NAME %s\n", g_test_name);
    } else if(strstr(buffer, "enable_data_stall")) {
        enable_data_stall = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"enable_data_stall %d\n", enable_data_stall);
    } else if(strstr(buffer, "enable_beacon_stuck")) {
        enable_beacon_stuck = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"enable_beacon_stuck %d\n", enable_beacon_stuck);
    } else if(strstr(buffer, "enable_client_disconnect")) {
        enable_client_disconnect = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"enable_client_disconnect %d\n", enable_client_disconnect);
    } else if(strstr(buffer, "enable_fail_to_connect")) {
        enable_fail_to_connect = atoi(val);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"enable_fail_to_connect %d\n", enable_fail_to_connect);
    } else if(strstr(buffer, "data_stall_threshold")) {
        char *endptr = NULL;
        errno = 0;
        float parsed = strtof(val, &endptr);
        if (endptr == val || *endptr != '\0' || errno == ERANGE) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG,
                "WARNING: data_stall_threshold value '%s' is not a valid number, falling back to default %.3f\n",
                val, (double)DATA_STALL_THRESHOLD_DEFAULT);
            data_stall_threshold = DATA_STALL_THRESHOLD_DEFAULT;
        } else {
            data_stall_threshold = parsed;
        }
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"data_stall_threshold %.6f\n", (double)data_stall_threshold);
    }
}

int parse_center_freqs(int *freqs, int max_freqs) {
    FILE *fp = popen("iw dev", "r");
    if (!fp) return 0;

    char line[256];
    int count = 0;
    while (fgets(line, sizeof(line), fp)) {
        char *center_ptr = strstr(line, "center1:");
        if (center_ptr) {
            int freq = 0;
            if (sscanf(center_ptr, "center1: %d MHz", &freq) == 1) {
                if (freq > 0 && count < max_freqs) {
                    freqs[count++] = freq;
                }
            }
        }
    }
    pclose(fp);
    return count;
}

void print_stamp()
{
       time_t now = time(NULL);
       struct tm *local_time = localtime(&now);
       log_message(LOG_LEVEL_AD_LIB_DEBUG,"\n\n===Timestamp: %s===\n", asctime(local_time));
}

void is_ath_build(){
        char buf[256];
        FILE *conf_fp = fopen(WIFI_CONF, "r");
        if (conf_fp == NULL) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Error opening WiFi conf file: %s\n", strerror(errno));
            goto end;
        }
        while (fgets(buf, sizeof(buf), conf_fp)) {
            if(strstr(buf, ATH_CONF_STR) != NULL) {
                if(conf_fp){
                        fclose(conf_fp);
                }
                ath_build = 1;
                goto end;
            }
        }
        if(conf_fp){
                fclose(conf_fp);
        }
end:
        return;
}

int check_log_dir_space_available()
{
    struct statvfs stat;
    if (statvfs(log_dir, &stat) != 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to get filesystem stats for %s\n", log_dir);
        return -1;
    }
    
    unsigned long long total_blocks = stat.f_blocks;
    unsigned long long avail_blocks = stat.f_bavail;
    
    if (total_blocks == 0) return -1;
    
    double avail_percent = (double)avail_blocks / (double)total_blocks * 100.0;
    
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Disk space check: %.2f%% available in %s\n", avail_percent, log_dir);
    
    return (avail_percent >= DISK_SPACE_THRESHOLD_PERCENT) ? 1 : 0;
}

/* delete_dir and create_log_dir moved to notification_processing.c */

void send_on_channel(int srcApp, int dstApp, int chanNum, int mstType, char *msg, int msgSize)
{
	struct meta_data meta = {
                .srcAppId = srcApp,
                .dstAppId = dstApp,
                .channelNum = chanNum,
                .MSGType = MSG_TYPE_DATA,
                .versionNum = VERSION_NUM_3,
                .headerLen = (uint16_t)sizeof(struct meta_data),
                .headerVersion = 2,
                .nextHeaderEnum = 0
        };
	size_t message_len = sizeof(struct meta_data) + msgSize;
	char* message = (char*)malloc(message_len);
	memcpy(message, &meta, sizeof(struct meta_data));
	if(msg){
		char* payload = message + sizeof(struct meta_data);
		memcpy(payload, msg, msgSize);
	}
	int ret = gwapp_transport_send_msg(message, message_len);
	if (ret != 0) {
                if(debug_lvl == 1) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"gwapp_transport_send_msg failed\n");
                        if (dstApp == APPID_AD_UNIT_TEST_APP) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"gwapp_transport_send_msg failed for AD Unit Test App\n");
                        }
                        if (dstApp == APPID_CIA) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"gwapp_transport_send_msg failed for CIA\n");
                        }
                }
        } else {
                if(debug_lvl == 1) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"gwapp_transport_send_msg Success\n");
                        if (dstApp == APPID_AD_UNIT_TEST_APP) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"gwapp_transport_send_msg Success for AD Unit Test App\n");
                        }
                        if (dstApp == APPID_CIA) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"gwapp_transport_send_msg Success for CIA\n");
                        }
                }
        }

        free(message);
}

void send_notification(int radio_id, int anomaly_cnt, int anom_hist_cnt, int band, int stamp, int type, int pkt_log)
{

    int option = 1;
    struct sockaddr_in serv_addr;
    int fd_Socket;
    char message[CMD_LEN];
    char timestamp_str[CMD_LEN];
    char *note_str = "Connectivity Anomaly detected on ";
    time_t now = time(NULL);
    char hist_str[INT_STR];
    char band_str[INT_STR];
    char *note_str1 = "Anomalies in last 10 iterations: ";
    char *note_str2 = "Anomaly detected on band: ";
    char *time_str = "Timestamp: ";
    char *log_str = "Logs saved at: ";
    char *type_str = "Anomaly Type: ";
    char *line_str = "\n";

    struct tm *local_time = localtime(&now);
    int note_length = 0;
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"stamp %d", stamp);
    strlcpy(timestamp_str, asctime(local_time), CMD_LEN);
    for(int i = 0; i < strlen(timestamp_str); i++) {
        if((isspace(timestamp_str[i])) || timestamp_str[i] == ':') {
            memcpy(&timestamp_str[i], "_", 1);
        }
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"time_stamp: %s\n", timestamp_str);

    create_log_dir(anomaly_cnt, timestamp_str);
    
    // Use band-specific reference file
    char *band_reference_path = NULL;
    if (band == BAND_2G) {
        band_reference_path = reference_wifistat_path_2g;
    } else if (band == BAND_5G) {
        band_reference_path = reference_wifistat_path_5g;
    } else if (band == BAND_6G) {
        band_reference_path = reference_wifistat_path_6g;
    }
    
    char current_wifistat_path[CMD_LEN];
    char rate_of_change_path[CMD_LEN];
    
    snprintf(current_wifistat_path, CMD_LEN, "%s/current_wifistats.txt", log_folder);
    snprintf(rate_of_change_path, CMD_LEN, "%s/rate_of_change_wifistats.txt", log_folder);
    
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Initializing FD socket\n");
    if ((fd_Socket = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"FD Socket creation error\n");
        return;
    }
    strlcpy(message, note_str, CMD_LEN);
    snprintf(hist_str, INT_STR, "%d", anom_hist_cnt);
    snprintf(band_str, INT_STR, "%dG", band);
    strlcat(message, radios[radio_id], CMD_LEN);
    strlcat(message, line_str, CMD_LEN);
    strlcat(message, note_str1, CMD_LEN);
    strlcat(message, hist_str, CMD_LEN);
    strlcat(message, line_str, CMD_LEN);
    strlcat(message, note_str2, CMD_LEN);
    strlcat(message, band_str, CMD_LEN);
    strlcat(message, line_str, CMD_LEN);
    strlcat(message, type_str, CMD_LEN);
    if(type == ANOM_BEACON_STUCK){
        strlcat(message, "BEACON STUCK", CMD_LEN);
        strlcat(message, line_str, CMD_LEN);
        strlcat(message, note_value, CMD_LEN);
    }
    if(type == ANOM_DATA_STALL){
        strlcat(message, "DATA STALL", CMD_LEN);
        strlcat(message, line_str, CMD_LEN);
        strlcat(message, note_value, CMD_LEN);
    }
    if(type == ANOM_DISCONNECT){
        strlcat(message, "DISCONNECT", CMD_LEN);
        strlcat(message, line_str, CMD_LEN);
        char disc_str[128];
        int disc = (int)((g_last_client_change < 0.0f) ? -g_last_client_change * inf_inter : g_last_client_change * inf_inter);
        
        // If disc == 0, update disconnect count using tx_12 and rx_12
        if (disc == 0) {
            disc = (int)((g_last_tx_mgmt_12 * inf_inter) + (g_last_rx_mgmt_12 * inf_inter));
        }
        
        snprintf(disc_str, sizeof(disc_str), "Number of Disconnections: %d", disc);
        strlcat(message, disc_str, CMD_LEN);
        strlcat(message, line_str, CMD_LEN);
    }
    if(type == ANOM_FAIL_CONNECT){
        strlcat(message, "FAIL TO CONNECT", CMD_LEN);
        strlcat(message, line_str, CMD_LEN);
    }
    strlcat(message, line_str, CMD_LEN);
    strlcat(message, time_str, CMD_LEN);
    strlcat(message, asctime(local_time), CMD_LEN);
    strlcat(message, log_str, CMD_LEN);
    strlcat(message, log_folder, CMD_LEN);
    strlcpy(note_message, message, CMD_LEN);

    char notif_path[CMD_LEN];
    fd_build_anomaly_log_path(notif_path, sizeof(notif_path));

    // Step 1: Save syslog (only for DISCONNECT or FAIL_CONNECT)
    if (type == ANOM_DISCONNECT || type == ANOM_FAIL_CONNECT) {
        save_syslog(notif_path);
    }

    // Step 2: Save buffer
    save_buffer(cir_buffer, radio_id, notif_path);
    
    // Step 3: Process syslog (only for DISCONNECT or FAIL_CONNECT)
    if (type == ANOM_DISCONNECT || type == ANOM_FAIL_CONNECT) {
        process_syslog(cur_sys_path, notif_path, type);
    }

        // Step 4: Capture wifistats
    if (capture_wifistats_to_file(radio_id, current_wifistat_path, pkt_log) == 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Saved wifistats to: %s\n", current_wifistat_path);
        
        // Calculate rate of change if band-specific reference exists
        if (band_reference_path && band_reference_path[0] != '\0') {
            calculate_rate_of_change(band_reference_path, current_wifistat_path, rate_of_change_path);
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Calculated rate of change using %dG reference: %s\n", band, band_reference_path);
            
            // Copy reference wifistat into the anomaly folder
            char ref_in_anomaly_path[CMD_LEN];
            snprintf(ref_in_anomaly_path, CMD_LEN, "%s/reference_wifistats.txt", log_folder);
            char cmd_ref_copy[CMD_LEN];
            snprintf(cmd_ref_copy, CMD_LEN, "cp %s %s", band_reference_path, ref_in_anomaly_path);
            system(cmd_ref_copy);
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Copied reference wifistats to anomaly folder: %s\n", ref_in_anomaly_path);
        }
        
        // Update band-specific reference file with current capture
        if (band_reference_path) {
            char cmd_copy[CMD_LEN];
            snprintf(cmd_copy, CMD_LEN, "cp %s %s", current_wifistat_path, band_reference_path);
            system(cmd_copy);
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Updated %dG reference wifistat file: %s\n", band, band_reference_path);
        }
    }
    

    send_logs_to_cloud_for(log_folder);
	note_length = strlen(message);
	send_on_channel(APPID_ANAMOLY_DETECTION, APPID_ANAMOLY_DETECTION, INFERENCE_DATA, MSG_TYPE_DATA, message, note_length);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = inet_addr(LOCAL_HOST);
    serv_addr.sin_port = htons(FD_PORT);
    setsockopt(fd_Socket, SOL_SOCKET, SO_REUSEADDR, &option, sizeof(int));
    sendto(fd_Socket, message, strlen(message),MSG_CONFIRM, (const struct sockaddr *) &serv_addr,sizeof(serv_addr));
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"\n\n\n====Anomaly notification_sent====\nNotification: %s\n\n\n", message);
    close(fd_Socket);
    if(enable_peer_stats && ath_build){
        AllPeerStats all_peer_stats;
        memset(&all_peer_stats, 0, sizeof(AllPeerStats));
        
        char peer_stats_raw_path[MAX_PATH_PEER];
        snprintf(peer_stats_raw_path, sizeof(peer_stats_raw_path), "%s%speer_stats.txt", log_folder, FWD_SLSH);
        int ret_peer_cnt = get_all_peer_stats(&all_peer_stats, peer_stats_raw_path);

        if (ret_peer_cnt >= 0) {
                
            classify_peers(&all_peer_stats);

            print_peer_stats(&all_peer_stats);

            char client_heatmap_path[MAX_PATH_PEER];
            snprintf(client_heatmap_path, sizeof(client_heatmap_path), "%s%sclient_heatmap.txt", log_folder, FWD_SLSH);

            int wret = write_peer_stats_to_file(&all_peer_stats, client_heatmap_path);
            if (wret == 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"Wrote peer stats to: %s\n", client_heatmap_path);
            } else {
                log_message(LOG_LEVEL_AD_LIB_DEBUG," Failed writing peer stats to: %s (errno=%d)\n", client_heatmap_path, errno);
            }
        } else {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "get_all_peer_stats() failed (ret=%d)\n", ret_peer_cnt);
        }
        free_all_peer_stats(&all_peer_stats);
    }
    
    // Check disk space and adjust effective_max_anomaly_count dynamically
    int space_check = check_log_dir_space_available();
    if (space_check == 0) {
        // Less than threshold space available - reduce to minimum
        if (effective_max_anomaly_count != MIN_ANOMALY_FOLDERS_ALL) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Disk space below %.1f%%, reducing effective_max_anomaly_count from %d to %d\n", 
                       DISK_SPACE_THRESHOLD_PERCENT, effective_max_anomaly_count, MIN_ANOMALY_FOLDERS_ALL);
            effective_max_anomaly_count = MIN_ANOMALY_FOLDERS_ALL;
        }
    } else if (space_check == 1) {
        // Threshold or more space available - restore to user's configured value
        if (effective_max_anomaly_count != max_anomaly_count) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Disk space recovered above %.1f%%, restoring effective_max_anomaly_count from %d to %d\n", 
                       DISK_SPACE_THRESHOLD_PERCENT, effective_max_anomaly_count, max_anomaly_count);
            effective_max_anomaly_count = max_anomaly_count;
        }
    }
    // If space_check == -1 (error), keep current effective_max_anomaly_count unchanged
    
    return;
}

void read_config()
{
	FILE *config;
	config = fopen(CONFIG_FILE, "r");
	char buffer[MAX_LEN];
	if(config == NULL){
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"Could not open config file \n");
		return;
	}
	while(fgets(buffer, MAX_LEN, config) !=NULL) {
		if(strstr(buffer, "#")) {
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"Comment\n");
		}
		else {
			parse_config(buffer);
		}
	}
    // test app
    if (g_test_level == 1) {
        if (g_test_label[0] == '\0' || g_test_name[0] == '\0') {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "WARNING: TEST_LEVEL=1 with missing TEST_LABEL or TEST_NAME, setting defaults\n");
            if (g_test_label[0] == '\0') {
                strlcpy(g_test_label, TEST_LABEL_PASS, sizeof(g_test_label));
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Set TEST_LABEL to default: %s\n", TEST_LABEL_PASS);
            }
            if (g_test_name[0] == '\0') {
                strlcpy(g_test_name, TEST_NAME_DEFAULT, sizeof(g_test_name));
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Set TEST_NAME to default: %s\n", TEST_NAME_DEFAULT);
            }
        }
    }
    
    // Validate buffer_capacity
    if (buffer_history < MIN_BUFFER) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "WARNING: buffer_capacity cannot be less than %d (current value: %d), setting to default: %d\n", MIN_BUFFER, buffer_history, DEFAULT_BUFFER);
        buffer_history = DEFAULT_BUFFER;
    }
    if (buffer_history > MAX_BUFFER) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "WARNING: buffer_capacity cannot exceed %d (current value: %d), setting to default: %d\n", MAX_BUFFER, buffer_history, DEFAULT_BUFFER);
        buffer_history = DEFAULT_BUFFER;
    }

    // Set default value for MAX_PEERS if not set in config file
    if (MAX_PEERS == 0) {
        MAX_PEERS = 512;
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Using default max_peer_count %d\n", MAX_PEERS);
    }
    
    // Validate max_anomaly_folders
    if (max_anomaly_count < MIN_ANOMALY_FOLDERS_ALL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "WARNING: max_anomaly_folders cannot be less than %d (current value: %d), setting to default: %d\n", MIN_ANOMALY_FOLDERS_ALL, max_anomaly_count, DEFAULT_MAX_ANOMALY_FOLDERS);
        max_anomaly_count = DEFAULT_MAX_ANOMALY_FOLDERS;
    }
    if (save_logs_to_usb == 0 && max_anomaly_count > MAX_ANOMALY_FOLDERS_LOCAL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "WARNING: max_anomaly_folders cannot exceed %d when save_logs_to_usb is disabled (current value: %d), setting to default: %d\n", MAX_ANOMALY_FOLDERS_LOCAL, max_anomaly_count, DEFAULT_MAX_ANOMALY_FOLDERS);
        max_anomaly_count = DEFAULT_MAX_ANOMALY_FOLDERS;
    }

    // Validate data_stall_threshold: must be a finite value in [0.0, 1.0]
    if (isnan(data_stall_threshold) || isinf(data_stall_threshold) ||
        data_stall_threshold < 0.0f || data_stall_threshold > 1.0f) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,
            "WARNING: data_stall_threshold must be in [0.0, 1.0] (current value: %.6f), setting to default: %.3f\n",
            (double)data_stall_threshold, (double)DATA_STALL_THRESHOLD_DEFAULT);
        data_stall_threshold = DATA_STALL_THRESHOLD_DEFAULT;
    }

    // Allocate anomaly_history and anomaly_itr arrays based on max_anomaly_count
    if (anomaly_history != NULL) {
        free(anomaly_history);
    }
    if (anomaly_itr != NULL) {
        free(anomaly_itr);
    }
    anomaly_history = (int*)calloc(max_anomaly_count, sizeof(int));
    anomaly_itr = (int*)calloc(max_anomaly_count, sizeof(int));
    
    if (anomaly_history == NULL || anomaly_itr == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"WARNING: Failed to allocate memory for anomaly arrays with size %d, retrying with default size %d\n", max_anomaly_count, DEFAULT_MAX_ANOMALY_FOLDERS);
        
        // Free any partially allocated memory
        if (anomaly_history != NULL) {
            free(anomaly_history);
            anomaly_history = NULL;
        }
        if (anomaly_itr != NULL) {
            free(anomaly_itr);
            anomaly_itr = NULL;
        }
        
        // Set to default size and retry allocation
        max_anomaly_count = DEFAULT_MAX_ANOMALY_FOLDERS;
        anomaly_history = (int*)calloc(DEFAULT_MAX_ANOMALY_FOLDERS, sizeof(int));
        anomaly_itr = (int*)calloc(DEFAULT_MAX_ANOMALY_FOLDERS, sizeof(int));
        
        if (anomaly_history == NULL || anomaly_itr == NULL) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"ERROR: Failed to allocate memory for anomaly arrays even with default size %d\n", DEFAULT_MAX_ANOMALY_FOLDERS);
            fclose(config);
            exit(1);
        }
        
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Successfully allocated anomaly arrays with default size %d\n", DEFAULT_MAX_ANOMALY_FOLDERS);
    }
    
    // Initialize effective_max_anomaly_count to user's configured value
    effective_max_anomaly_count = max_anomaly_count;
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Initialized effective_max_anomaly_count to %d\n", effective_max_anomaly_count);
    
    fclose(config);
}

/* load_thresholds and process_output moved to postprocess.c */


int save_buffer(float *buf, int radio_id, const char *notif_path)
{
    char log_str[LOG_LEN];
    FILE *log_file;

    int buffer_itr = buffer_len / stats_count;
    int start_idx  = cur_cir_idx % buffer_len;
    int end_idx    = (start_idx + stats_count) % buffer_len;

    if (debug_lvl == 1)
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Circular buffer Log file: %s buffer Itr: %d:Len:%d \n", notif_path, buffer_itr, buffer_len);

    log_file = fopen(notif_path, "w");
    if (log_file == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Could not open log file\n");
        return -1;
    }

    fprintf(log_file, "===Anomaly detected on radio band %dG===\n", cur_bands[radio_id]);
    fprintf(log_file, "%s\n", note_message);

    for (int i = 0; i < buffer_itr; i++) {
        fprintf(log_file, "===Iteration %d===\n", i);

        int wr_idx = 0, wrt_cnt = 0, j = 0;
        if (debug_lvl == 1)
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"start idx %d, end idx %d buf len %d\n",
                        start_idx, end_idx, buffer_len);

        for (int idx = 0; idx < radio_count; idx++) {
            fprintf(log_file, "\nRadio Band %d: ", cur_bands[idx]);
            int itr_start = start_idx + (idx * CRITICAL_STAT_LEN);
            int itr_end   = itr_start + CRITICAL_STAT_LEN;
            int tag_idx   = 0;
            for (j = itr_start; j < itr_end; j++) {
                int buf_idx = j % buffer_len;
                wrt_cnt = snprintf(&log_str[wr_idx], LOG_LEN, "%d:%f \t", tag_idx, cir_buffer[buf_idx]);
                wr_idx += wrt_cnt;
                tag_idx++;
            }
            fprintf(log_file, "%s\n", log_str);
            memset(log_str, '\0', LOG_LEN);
            wrt_cnt = 0;
            wr_idx  = 0;
        }

        memset(log_str, '\0', LOG_LEN);
        start_idx = (start_idx + stats_count) % buffer_len;
        end_idx   = (end_idx   + stats_count) % buffer_len;
    }

    fclose(log_file);
    return 0;
}

void send_note(int rad_id, int band, int type)
{
	int i = 0, anomaly_hist_cnt = 0;
	int cur_anom_cnt = itr_cnt % max_anomaly_count;
	anomaly_history[cur_anom_cnt] = 1;
	for(i = 0; i < max_anomaly_count; i++)
	{
		anomaly_hist_cnt += anomaly_history[i];
	}
        send_notification(rad_id, anomaly_count % effective_max_anomaly_count, anomaly_hist_cnt, band, stamp, type, enable_pkt);
	anomaly_count++;
}

/* unload_model, fd_nwaios_callback, ensure_nwaios_init, load_model_for_band, run_inference moved to model_inferencing.c */
/* get_file_length, load_values, normalize, pre_process moved to preprocess.c */

int gwapp_verify_license()
{
	log_message(LOG_LEVEL_AD_LIB_DEBUG,"Anomaly Detection License Verification Failed");
	exit(0);
}

int gwapp_transport_recv_msg(char* payload, size_t payload_len)
{
    struct meta_data* meta_ptr = (struct meta_data*)payload;
    log_message(LOG_LEVEL_AD_LIB_DEBUG,
        "RX hdr: src=%u dst=%u ch=%u type=%u ver=%u msg_id=%u sub=%u len=%u (payload_len=%zu)",
        meta_ptr->srcAppId, meta_ptr->dstAppId, meta_ptr->channelNum, meta_ptr->MSGType,
        meta_ptr->versionNum, meta_ptr->appMsgID, meta_ptr->subCategory, meta_ptr->len, payload_len);

    /* GWApps 1.2: use headerLen to locate payload when versionNum >= 3 */
    size_t hdr_len = (meta_ptr->versionNum >= 3)
                     ? (size_t)meta_ptr->headerLen
                     : sizeof(struct meta_data);

    uint16_t src = meta_ptr->srcAppId;
    uint16_t msg_id = meta_ptr->appMsgID;
    uint16_t sub_category = meta_ptr->subCategory;

    // Handle keepalive inquiry from LCM
    if (src == APPID_LCM) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Message received from LCM");

        char* payload_data = payload + hdr_len;
        size_t payload_data_len = payload_len - hdr_len;
        
        int ret = gwapp_keepalive_callback(APPID_ANAMOLY_DETECTION, payload_data, payload_data_len);
        if (ret == 0) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Keepalive response sent to LCM\n");
        } else {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to send keepalive response to LCM\n");
        }
        return 0;
    }

    // Handle CIA response for log upload
    if (src == APPID_CIA) {
        if (msg_id == APP_MSG_DATA_COLLECTION) {
                if (sub_category == APP_MSG_SUB_START) {
                        g_test_level = 1;
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "DATA COLLECTION START received from appId=%u", src);
                } else if (sub_category == APP_MSG_SUB_STOP) {
                        g_test_level = 0;
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "DATA COLLECTION STOP received (appId=%u)", src);
                }
                return 0;
        }

        // debuggability
        if (msg_id == APP_MSG_DEBUG) {
                if (sub_category == APP_MSG_SUB_START) {
                        debug_start();
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "DEBUG START received from appId=%u", src);
                } else if (sub_category == APP_MSG_SUB_STOP) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "DEBUG STOP received (appId=%u)", src);
                        debug_stop();
                }
                return 0;
        }

        /* Parse CIA response frame: [meta][cloud_meta][status][headers_len][headers][body_len][body] */
        size_t offset = hdr_len;

        // Dynamically calculate cloud_meta_data length
        const char* cloud_meta_ptr = payload + offset;
        size_t cloud_available = payload_len - offset;
        size_t cloud_len = parse_cloud_meta_length(cloud_meta_ptr, cloud_available);

        if (cloud_len == 0) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to parse cloud_meta_data length\n");
            return 0;
        }

        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Parsed cloud_meta_data length: %zu bytes\n", cloud_len);

        if (payload_len < offset + cloud_len + sizeof(uint32_t) * 3) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Response too short to contain sections (need %zu, have %zu)\n",
                       offset + cloud_len + sizeof(uint32_t) * 3, payload_len);
            return 0;
        }

        const char* base = payload;
        const char* p = base + offset + cloud_len;

        uint32_t status = 0;
        uint32_t headers_len = 0;
        uint32_t body_len = 0;

        memcpy(&status, p, sizeof(uint32_t)); p += sizeof(uint32_t);
        memcpy(&headers_len, p, sizeof(uint32_t)); p += sizeof(uint32_t);

        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Parsed status: %u, headers_len: %u\n", status, headers_len);

        if (payload_len < (size_t)(p - base) + headers_len + sizeof(uint32_t)) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Malformed response: headers exceed buffer (need %zu, have %zu)\n",
                       (size_t)(p - base) + headers_len + sizeof(uint32_t), payload_len);
            return 0;
        }
        p += headers_len;

        memcpy(&body_len, p, sizeof(uint32_t)); p += sizeof(uint32_t);
        if (payload_len < (size_t)(p - base) + body_len) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Malformed response: body exceeds buffer (need %zu, have %zu)\n",
                       (size_t)(p - base) + body_len, payload_len);
            return 0;
        }
        const char* body_ptr = p;

        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Status: %u\n", status);
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Headers length: %u, Body length: %u\n", headers_len, body_len);

        /* Copy body to a temporary null-terminated buffer for parsing and pretty-print */
        char* body_json = NULL;
        if (body_len > 0) {
            body_json = (char*)malloc(body_len + 1);
            if (body_json) {
                memcpy(body_json, body_ptr, body_len);
                body_json[body_len] = '\0';

                log_message(LOG_LEVEL_AD_LIB_DEBUG, "\n=== CIA RESPONSE RECEIVED ===\n");
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Status: %u %s\n", status, (status == 200) ? "(Success)" : "(Error)");
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Headers length: %u, Body length: %u\n", headers_len, body_len);
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Response Body: %s\n", body_json);

                free(body_json);
            }
        } else {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "\n=== CIA RESPONSE RECEIVED ===\n");
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Status: %u %s\n", status, (status == 200) ? "(Success)" : "(Error)");
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "No response body\n");
        }

        // Parse service_name from cloud_meta_data to determine which queue to clean
        char service_name[33] = {0};
        if (cloud_len >= 32) {
            memcpy(service_name, cloud_meta_ptr, 32);
            // Trim null padding
            for (int i = 31; i >= 0; i--) {
                if (service_name[i] == '\0' || service_name[i] == ' ') {
                    service_name[i] = '\0';
                } else {
                    break;
                }
            }
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Parsed service_name from cloud_meta_data: '%s'\n", service_name);
        }

        // Handle success/failure - cleanup tar file on success
        if (status == 200) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "CIA confirmed successful upload\n");

            // Determine which queue to clean based on service_name
            if (strcmp(service_name, "DataCollection") == 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Cleaning up TL1 queue (DataCollection)\n");
                cleanup_pending_upload_on_success(status, UPLOAD_QUEUE_TL1);
            } else if (strcmp(service_name, "UploadSnapshot") == 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Cleaning up regular log queue (UploadSnapshot)\n");
                cleanup_pending_upload_on_success(status, UPLOAD_QUEUE_REGULAR);
            } else if (strcmp(service_name, "LogSummarization") == 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Cleaning up LogSummarization queue\n");
                cleanup_pending_upload_on_success(status, UPLOAD_QUEUE_LOGSUM);
            } else {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Unknown service_name '%s', defaulting to regular queue cleanup\n", service_name);
                cleanup_pending_upload_on_success(status, UPLOAD_QUEUE_REGULAR);
            }
        } else {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "CIA upload failed with status %u\n", status);
        }

        return 0;
    }

    if (src != APPID_CIA && msg_id == APP_MSG_DATA_COLLECTION) {
        if (sub_category == APP_MSG_SUB_START) {
                g_test_level = 1;
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "DATA COLLECTION START received from appId=%u", src);
        } else if (sub_category == APP_MSG_SUB_STOP) {
                g_test_level = 0;
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "DATA COLLECTION STOP received (appId=%u)", src);
        }
        return 0;
    }

    // debuggability
    if (src != APPID_CIA && msg_id == APP_MSG_DEBUG) {
        if (sub_category == APP_MSG_SUB_START) {
                debug_start();
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "DEBUG START received from appId=%u", src);
        } else if (sub_category == APP_MSG_SUB_STOP) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "DEBUG STOP received (appId=%u)", src);
                debug_stop();
        }
        return 0;
    }

    if (src == APPID_TELEMETRY_SERV_APP) {

        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Made it to TSA");
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Test level is set to=%u", g_test_level);

        if (g_test_level == 2) {
                return 0;
        }

        char* band_tlv = (char*)((char*)meta_ptr + hdr_len);
        int index = 0;

        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Received Message in AD APP from telemetry Agent payload length:%lu", payload_len);

        uint8_t type = band_tlv[index];
        uint8_t length = band_tlv[index + 1];
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"type = %d, length = %d", type, length);

        if (type == BAND_TLV) {
                bands = (int*)(band_tlv + 2);
        } else {
                return 0;
        }

        float* all_stats = (float*)((uint8_t*) band_tlv + length);
        fprintf(stderr, "all_stats done\n");
        length = (int)hdr_len + length;
        fprintf(stderr, "length done %d\n", length);
        
        if  (payload_len <= length) {
                return 0;
        }

        radio_count = (payload_len - length) / (sizeof(float) * CRITICAL_STAT_LEN);

        for (int j = 0; j < radio_count; j++) {
                if (debug_lvl == 1)
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Radio #%d band:%d", j, bands[j]);
                cur_bands[j] = bands[j];
        }

        stats_count = radio_count * CRITICAL_STAT_LEN;
        if(debug_lvl == 1) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"radio_count: %d arr len: %d\n", radio_count, stats_count);
        }

        if (cir_buffer == NULL) {
                buffer_len = (CRITICAL_STAT_LEN * radio_count) * buffer_history;
                cir_buffer = (float*) malloc(buffer_len * sizeof(float));
        }
        if(prev_m1_rate == NULL){
                prev_m1_rate = (float *) malloc(radio_count * sizeof(float));
                prev_m3_rate = (float *) malloc(radio_count * sizeof(float));
                prev_m1_m3_rate = (float *) malloc(radio_count * sizeof(float));
        }

        cur_cir_idx = cur_cir_idx % buffer_len;
        if(debug_lvl == 1) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"cur_cir_idx %d\n", cur_cir_idx);
        }
        for (int i = 0; i < radio_count; i++) {
            for (int j = 0; j < CRITICAL_STAT_LEN; j++) {
                if(debug_lvl == 1) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"FD_app==all stats idx :%d %f==\t", j + (i * CRITICAL_STAT_LEN) ,all_stats[j + (i * CRITICAL_STAT_LEN)]);
                }
                cir_buffer[cur_cir_idx++] = all_stats[j + (i * CRITICAL_STAT_LEN)];
            }
        }
        
        pre_process(radio_count, all_stats, inf_inter);

        if(debug_lvl == 1){
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"cur cir idx: %d\n", cur_cir_idx);
        }

        return 0;
    }
    // unit test app
    if (src == APPID_AD_UNIT_TEST_APP && msg_id != APP_MSG_DEBUG && msg_id != APP_MSG_DATA_COLLECTION) {
        const char* json_start = (const char*)payload + hdr_len;
        size_t json_len = payload_len - hdr_len;
        if (json_len == 0) return 0;

        // Copy & NUL-terminate
        char* json_buf = (char*)malloc(json_len + 1);
        if (!json_buf) return 0;
        memcpy(json_buf, json_start, json_len);
        json_buf[json_len] = '\0';

        struct json_object* jobj = json_tokener_parse(json_buf);
        free(json_buf);
        if (!jobj) return 0;

        // handshake and init check
        struct json_object *j_level = NULL, *j_type = NULL, *j_msgid = NULL, *j_control = NULL;
        json_object_object_get_ex(jobj, "TEST_LEVEL", &j_level);
        json_object_object_get_ex(jobj, "message_type", &j_type);
        json_object_object_get_ex(jobj, "message_id", &j_msgid);
        json_object_object_get_ex(jobj, "control", &j_control);

        const char* control = j_control ? json_object_get_string(j_control) : "";
        if (control && strcmp(control, "STOP_BROADCAST") == 0) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Received STOP_BROADCAST command");
            g_broadcast_test_level = 0;
            json_object_put(jobj);
            return 0;
        }

        const char* tl = j_level ? json_object_get_string(j_level) : "2";
        const char* message_id = j_msgid ? json_object_get_string(j_msgid) : "";

        // reply pass for handshake
        struct json_object *j_label = NULL;
        json_object_object_get_ex(jobj, "model_inference_label", &j_label);
        const char* expected_label = j_label ? json_object_get_string(j_label) : "";
        if (expected_label && strcmp(expected_label, "handshake") == 0) {
            // respond "pass" quickly to unblock the validator's first exchange
            char ts[32];
            time_t now = time(NULL);
            struct tm tm_utc;
            gmtime_r(&now, &tm_utc);
            strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);

            char resp[256];
            int n = snprintf(resp, sizeof(resp),
                "{"
                  "\"TEST_LEVEL\":\"2\","
                  "\"message_id\":\"%s\","
                  "\"result\":\"pass\","
                  "\"timestamp\":\"%s\""
                "}",
                (message_id ? message_id : ""), ts);
            send_on_channel(APPID_ANAMOLY_DETECTION, APPID_AD_UNIT_TEST_APP, INPUT_PARAMS, MSG_TYPE_DATA, resp, n);
            json_object_put(jobj);
            return 0;
        }

        struct json_object *j_band = NULL, *j_stats = NULL;
        json_object_object_get_ex(jobj, "band", &j_band);
        json_object_object_get_ex(jobj, "all_stats", &j_stats);

        int band = 0;
        if (j_band) {
            if (json_object_is_type(j_band, json_type_int)) {
                band = json_object_get_int(j_band);
            } else {
                const char* bs = json_object_get_string(j_band);
                if (bs && (bs[0] == '2' || bs[0] == '5' || bs[0] == '6')) {
                    band = bs[0] - '0';
                }
            }
        }
        if (band != 2 && band != 5 && band != 6) band = 5;

        float all_stats[CRITICAL_STAT_LEN] = {0};
        if (!j_stats
            || !json_object_is_type(j_stats, json_type_array)
            || json_object_array_length(j_stats) < CRITICAL_STAT_LEN) {
            json_object_put(jobj);
            return 0;
        }
        for (int i = 0; i < CRITICAL_STAT_LEN; i++) {
            struct json_object* jv = json_object_array_get_idx(j_stats, i);
            all_stats[i] = (float)json_object_get_double(jv);
        }

        // fields from validator
        struct json_object *j_cycle = NULL, *j_idx = NULL, *j_first = NULL;
        json_object_object_get_ex(jobj, "cycle", &j_cycle);
        json_object_object_get_ex(jobj, "sample_index", &j_idx);
        json_object_object_get_ex(jobj, "first_in_cycle", &j_first);

        int new_cycle_no = g_tl2_cycle_no;
        int is_cycle_start = 0;

        // If cycle number is provided and changes -> new cycle
        if (j_cycle && json_object_is_type(j_cycle, json_type_int)) {
            new_cycle_no = json_object_get_int(j_cycle);
            if (new_cycle_no != g_tl2_cycle_no) {
                is_cycle_start = 1;
            }
        }

        if (is_cycle_start) {
            // clears all per-band prev + seen flags
            tl2_begin_new_cycle();           
            g_tl2_cycle_no = new_cycle_no;
        }

        // pretend we have 1 radio with 'band'
        radio_count = 1;
        cur_bands[0] = band;

        if (cir_buffer == NULL) {
            buffer_len = (CRITICAL_STAT_LEN * radio_count) * buffer_history;
            cir_buffer = (float*) malloc(buffer_len * sizeof(float));
        }
        cur_cir_idx = cur_cir_idx % buffer_len;
        for (int j = 0; j < CRITICAL_STAT_LEN; j++) {
            cir_buffer[cur_cir_idx++] = all_stats[j];
        }

        strlcpy(g_tl2_expected_label[0], (expected_label ? expected_label : ""), sizeof(g_tl2_expected_label[0]));
        strlcpy(g_tl2_message_id[0], (message_id ? message_id : ""), sizeof(g_tl2_message_id[0]));

        // We always pretend 1 radio in TL=2 mode
        int b = band;

        // first arrival PER BAND per cycle should auto-PASS
        if (!g_tl2_seen_first_by_band[b]) {
            // Ensure per-band previous is cleared so pre_process() treats this as warm-up
            tl2_clear_cycle_state_for_band(b);

            // ---- Swap-in per-band state for pre_process() warm-up
            float *saved_prev = prev_itr;
            int    saved_prev_cli = prev_cli_count;

            prev_itr = g_prev_itr_by_band[b];      // should be NULL now
            prev_cli_count = g_prev_cli_by_band[b];

            // Seed baseline (pre_process will see prev_itr == NULL and only initialize)
            pre_process(1, all_stats, inf_inter);

            // Store back per-band state updated by pre_process
            g_prev_itr_by_band[b] = prev_itr;
            g_prev_cli_by_band[b] = prev_cli_count;

            // Restore globals
            prev_itr = saved_prev;
            prev_cli_count = saved_prev_cli;

            // Immediately respond "pass" to the validator for this message
            send_tl2_result_for(0 /*rad_id*/, g_tl2_message_id[0], TEST_LABEL_PASS, TEST_LABEL_PASS);
            g_tl2_message_id[0][0] = '\0';
            g_tl2_expected_label[0][0] = '\0';
            g_tl2_pending[0] = 0;

            g_tl2_seen_first_by_band[b] = 1;

            json_object_put(jobj);
            return 0; 
        }

        // Normal TL=2 path for subsequent samples (band already initialized this cycle)
        g_tl2_pending[0] = 1;

        // TL=2: per-band prev buffer swap-in
        float *saved_prev_itr = prev_itr;
        int saved_prev_cli = prev_cli_count;

        prev_itr = g_prev_itr_by_band[b]; // load per-band prev
        prev_cli_count = g_prev_cli_by_band[b];

        pre_process(1, all_stats, inf_inter);

        // store back per-band state updated by pre_process
        g_prev_itr_by_band[b] = prev_itr;
        g_prev_cli_by_band[b] = prev_cli_count;

        // restore globals so TL=1 path (telemetry agent) is unaffected
        prev_itr = saved_prev_itr;
        prev_cli_count = saved_prev_cli;

        json_object_put(jobj);
        return 0;
    }

    return 0;
}

void input_timer_handler(int signum);
void reset_timer();

void reset_timer()
{
        struct itimerval timer;
        timer.it_value.tv_sec = inf_inter;
        timer.it_value.tv_usec = 0;
        timer.it_interval.tv_sec = inf_inter;
        timer.it_interval.tv_usec = 0;
        setitimer(ITIMER_REAL, &timer, NULL);
}

void send_test_level_broadcast(void) {
    if (g_test_level != 1 && g_test_level != 2) return;
    
    char ts[32];
    time_t now = time(NULL);
    struct tm tm_utc;
    gmtime_r(&now, &tm_utc);
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);

    char buf[256];
    int n = snprintf(buf, sizeof(buf),
        "{"
          "\"message_type\":\"TEST_LEVEL_BROADCAST\","
          "\"TEST_LEVEL\":\"%d\","
          "\"timestamp\":\"%s\""
        "}", g_test_level, ts);

    if (n > 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Broadcasting TEST_LEVEL=%d", g_test_level);
        
        // Route to the appropriate CIA service based on TEST_LEVEL
        if (g_test_level == 1) {
            send_json_to_cia("DataCollection", buf, n);
        } else if (g_test_level == 2) {
            send_json_to_cia("UnitTest", buf, n);
        }
    }
}

void input_timer_handler(int signum)
{
        if (g_debug_active) {
                debug_rotate_and_send();
        }

        if (g_broadcast_test_level && (g_test_level == 1 || g_test_level == 2)) {
            send_test_level_broadcast();
        }

        if (g_test_level == 2) {
            reset_timer();
            return;
        }

        send_on_channel(APPID_ANAMOLY_DETECTION, APPID_TELEMETRY_SERV_APP, INPUT_PARAMS, MSG_TYPE_DATA, NULL, 0);

        reset_timer();

}

void ad_shutdown_signal_handler(int signum)
{
	log_message(LOG_LEVEL_AD_LIB_DEBUG,"Received signal %d, shutting down,Generating Core\n", signum);
	if (chdir("/tmp") != 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "chdir");
	}
        gwapp_transport_stop(APPID_ANAMOLY_DETECTION);
	abort();
}

void ad_graceful_shutdown_handler(int signum)
{
	log_message(LOG_LEVEL_AD_LIB_DEBUG,"Received signal %d, shutting down gracefully\n", signum);
        gwapp_transport_stop(APPID_ANAMOLY_DETECTION);
	exit(0);
}


int main(int argc, char *argv[])
{
	setvbuf(stdout, NULL, _IONBF, 0);
	setvbuf(stderr, NULL, _IONBF, 0);

	char name[16];
	struct rlimit rl;
	rl.rlim_cur = RLIM_INFINITY;
	rl.rlim_max = RLIM_INFINITY;
	setrlimit(RLIMIT_CORE, &rl);

	if (prctl(PR_GET_NAME, name) == 0) {
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"Process name: %s\n", name);
	} else {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "prctl");
	}
	
	signal(SIGSEGV, ad_shutdown_signal_handler);
	signal(SIGFPE,  ad_shutdown_signal_handler);
	signal(SIGILL,  ad_shutdown_signal_handler);
	signal(SIGBUS,  ad_shutdown_signal_handler);
	signal(SIGINT,  ad_graceful_shutdown_handler);
	signal(SIGTERM, ad_graceful_shutdown_handler);

#ifdef LICENSE_CHECK_13_0
	uint32_t fid_to_check = AD_FID;
	int resp = verify_license(fid_to_check);
	if (resp) {
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"Anomaly Detection License Verification Failed");
		return 0;
	} else{
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"Anomaly Detection License Verification successful\n");
	}
#endif
	uint32_t fid_to_check = AD_FID;
	int ret = gwapps_license_lib_init(fid_to_check, gwapp_verify_license);
	if(ret != 0) {
		if(ret == ERR_LICENSE_VERIFICATION_LIB_NOT_FOUND) {
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"License library init failed! Library not found\n");
		} else {
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"License verification failed with error code: %d\n", ret);
		}
		_exit(1);
	}
        read_config();
	is_ath_build();
	if(enable_pkt)
		start_pkt_log();

	uint16_t appId = APPID_ANAMOLY_DETECTION;
	gwapp_transport_init(appId, gwapp_transport_recv_msg);
        

	int itr_len = ((CRITICAL_STAT_LEN) * MAX_RADIOS);
	stats_len = itr_len * sizeof(float);

    // Check if USB is mounted and reset hostapd log if it exists
	if (save_logs_to_usb == 1) {
		log_message(LOG_LEVEL_AD_LIB_DEBUG, "Mounted USB configured with hostapd.log, resetting log\n");
		reset_syslog();
	} else {
		log_message(LOG_LEVEL_AD_LIB_DEBUG, "No mounted USB with hostapd.log configured\n");
	}

    // Always start timer if we need to broadcast test level, or if in normal operation (not TL2)
    if (g_test_level != 2 || g_broadcast_test_level) {
        reset_timer(inf_inter);
        signal(SIGALRM, input_timer_handler);
    }

	while(1){
		pause();
	}
	gwapp_transport_stop(appId);
}
