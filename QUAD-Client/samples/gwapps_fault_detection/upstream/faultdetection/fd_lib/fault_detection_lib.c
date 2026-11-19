/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <sys/sysinfo.h>
#include <pthread.h>
#include <qcatools_lib.h>
//#include <netlink/attr.h>
#include <wlan_stats_define.h>
#include <stats_lib.h>
#include "htt.h"
#include "htt_stats.h"
#include "apstats.h"
#include "fault_detection_lib.h"
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <stdatomic.h>
#include <wasm_export.h>
#include <dlfcn.h>
#include "transport_client.h"
#include "telemetry_service_app.h"
#define MAX_RADIOS 5
#define MAC_ADDRESS_LEN_IN_CHARS 18
#define TOP_OUTPUT_LEN 1024
#define TOP_CMD_LEN 300
#define VAP_RADIO_LEN_MAX 16
#define HTT_MAX_STRING_LEN 1000
#define LOCAL_HOST "127.0.0.1"
#define CMD_LEN 1024
#define FILE_PATH_LEN 1024
#define PPDU_OK_IDX 28
#define FW_MGMT_TX_IDX 30
#define HW_ID_0_IDX 2
#define HW_ID_4_IDX 15
#define LINK_COLON ":"
#define IFACE_STR "Interface"
#define WLAN_STR "wlan"
#define LINK_STR "link "
#define MAX_INTERFACES 4
#define CRITICAL_STAT_COUNT 8
#define WIFI_CONF "/etc/config/wireless"
#define ATH_CONF_STR "config smp_affinity"

float *stats_arr;
int *bands_arr;
static int radios_count;
static int ath_radios_count;
volatile int done = 0;
int cca_num = 0;
static char radios[MAX_RADIOS][VAP_RADIO_LEN_MAX];
static char radio_macs[MAX_RADIOS][MAC_ADDRESS_LEN_IN_CHARS];
int critical_stat[] = {3, 1, 48, 8, 37, 10, 70, 73};
int stat_idx = 0;
int band_idx = 0;
int total_clients = 0;

size_t g_strlcpy(char *dst, const char *src, size_t size)
{
    size_t srclen = strlen(src);

    if (size) {
        size_t n = (srclen >= size) ? (size - 1) : srclen;
        memcpy(dst, src, n);
        dst[n] = '\0';
    }
    return srclen;
}
/*
 *Parse the tlv for the type and call the appropriate function
 */
void *col;
int hw_id = 100;
// Global handles for dynamically loaded libraries
void *nl3_handle = NULL;
void *gennl_handle = NULL;
void *qcanl_handle = NULL;
void *qca_tools_handle = NULL;
void *apstats_handle = NULL;
void *wifistats_handle = NULL;
void *wlanfw_handle = NULL;
void *stats_handle = NULL;

void lib_init(TelemetryServiceAPPCallbacks *callbacks);
static TelemetryServiceAPPCallbacks local_callbacks;

// Function to load all required libraries
int ad_load_wifi_libraries();
// Function to close all loaded libraries
void ad_close_wifi_libraries();


void log_message(LogLevel level, const char *format, ...)
{
    static int debug_enabled = -1;
    if (debug_enabled == -1) {
        const char *env = getenv("DEBUG_ENABLED");
        debug_enabled = (env && strcmp(env, "1") == 0) ? 1 : 0;
    }
    if (!debug_enabled && level < LOG_LEVEL_AD_LIB_WARN) {
        return;
    }

    const char *level_strings[] = { "DEBUG", "INFO", "WARN", "ERROR" };
    time_t now = time(NULL);
    char time_str[20];
    strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", localtime(&now));

    va_list args;
    va_start(args, format);
    fprintf(stderr, "[%s] [%s] ", time_str, level_strings[level]);
    vfprintf(stderr, format, args);
    fprintf(stderr, "\n");
    va_end(args);
}



char stat_folder_prefix[] = "/sys/kernel/debug/ath12k/";
char suffix_echo[] = "/mac0/htt_stats_type";
char suffix_read[] = "/mac0/htt_stats";
char suffix_host_read[] = "/mac0/dump_mgmt_stats";

char** ifaces = NULL;
int link_count[MAX_INTERFACES];
int interface_count = 0;
int i = 0;

void get_value_stat_37(char *folder_name, int curr_radio_index)
{
        char echo_path[FILE_PATH_LEN];
        char read_path[FILE_PATH_LEN];
        FILE *echo_file = NULL;
        FILE *read_file = NULL;
        char stat_buf[CMD_LEN];
        int freq_val = 0;

        snprintf(echo_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_echo);
        snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_read);

	char echo_cmd[CMD_LEN];
        snprintf(echo_cmd, sizeof(echo_cmd), "echo 37 > %s", echo_path);
        echo_file = popen(echo_cmd, "w");
        if (echo_file == NULL) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run echo command: %s\n", echo_cmd);
                return;
        }
        pclose(echo_file);

        read_file = fopen(read_path, "r");
        if(read_file == NULL) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not open read file: %s\n", read_path);
                return;
        }
        while(fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
                if(strstr(stat_buf, "operating center freq")){
                        char *center_freq = strstr(stat_buf,"=");
                        freq_val = atoi(&center_freq[2]);
                        
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"center freq: %d\n", freq_val);
                        
                        bands_arr[band_idx++] = freq_val /1000;
                        break;
                }
        }
        fclose(read_file);
}

void get_value_stat_1(char *folder_name, int curr_radio_index)
{
        char echo_path[FILE_PATH_LEN];
        char read_path[FILE_PATH_LEN];
        FILE *echo_file = NULL;
        FILE *read_file = NULL;
        char stat_buf[CMD_LEN];
        int xretry_val = 0;
        int ppdu_val = 0;
        int host_stat_index = curr_radio_index * CRITICAL_STAT_LEN;

        snprintf(echo_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_echo);
        snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_read);

        char echo_cmd[CMD_LEN];
        snprintf(echo_cmd, sizeof(echo_cmd), "echo 1 > %s", echo_path);
        echo_file = popen(echo_cmd, "w");
        if (echo_file == NULL) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run echo command: %s\n", echo_cmd);
                return;
        }
        pclose(echo_file);

        read_file = fopen(read_path, "r");
        if (read_file == NULL) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not open read file: %s\n", read_path);
                return;
        }
        while(fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
                if(strstr(stat_buf, "ppdu_ok")){
                        char *ppdu = strstr(stat_buf,"=");
                        ppdu_val = atoi(&ppdu[2]);
                        
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"ppdu_ok: %d\n", ppdu_val);
                        
                } else if(strstr(stat_buf, "tx_xretry")){
                        char *xretry = strstr(stat_buf,"=");
                        xretry_val = atoi(&xretry[2]);
                        
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"tx_xretry: %d\n", xretry_val);
                        
                }
        }
        fclose(read_file);
        stats_arr[host_stat_index + ATHSTAT_PPDU_OK] = ppdu_val;
        stats_arr[host_stat_index + ATHSTAT_TX_XRETRY] = xretry_val;
	
	        log_message(LOG_LEVEL_AD_LIB_DEBUG,"stat count %d\n", stat_idx);
}

void get_value_stat_8(char *folder_name, int curr_radio_index)
{
        char echo_path[FILE_PATH_LEN];
        char read_path[FILE_PATH_LEN];
        FILE *echo_file = NULL;
        FILE *read_file = NULL;
        char stat_buf[CMD_LEN];
        int m1_pack = 0;
        int m1_success = 0;
        int m3_pack = 0;
        int m3_success = 0;
        int host_stat_index = curr_radio_index * CRITICAL_STAT_LEN;

        snprintf(echo_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_echo);
        snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_read);

        char echo_cmd[CMD_LEN];
        snprintf(echo_cmd, sizeof(echo_cmd), "echo 8 > %s", echo_path);
        echo_file = popen(echo_cmd, "w");
        if (echo_file == NULL) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run echo command: %s\n", echo_cmd);
            return;
        }
        pclose(echo_file);

        read_file = fopen(read_path, "r");
        if (read_file == NULL) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not open read file: %s\n", read_path);
                return;
        }
        while(fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
                if(strstr(stat_buf, "m1_packets")){
                        char *m1_pstr = strstr(stat_buf,"=");
                        m1_pack = atoi(&m1_pstr[2]);
                        
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"m1_pack %d\n", m1_pack);
                        
                } else if(strstr(stat_buf, "m3_packets")){
                        char *m3_pstr = strstr(stat_buf,"=");
                        m3_pack = atoi(&m3_pstr[2]);
                        
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"m3_pack %d\n", m3_pack);
                        
                } else if(strstr(stat_buf, "m1_success")){
                        char *m1_sstr = strstr(stat_buf,"=");
                        m1_success = atoi(&m1_sstr[2]);
                        
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"m1_success %d\n", m1_success);
                        
                } else if(strstr(stat_buf, "m3_success")){
                        char *m3_sstr = strstr(stat_buf,"=");
                        m3_success = atoi(&m3_sstr[2]);
                        
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"m3_success %d\n", m3_success);
                        
                }
        }
        fclose(read_file);
        stats_arr[host_stat_index + ATHSTAT_M1_PACKETS] = m1_pack;
        stats_arr[host_stat_index + ATHSTAT_M3_PACKETS] = m3_pack;
        stats_arr[host_stat_index + ATHSTAT_M1_SUCCESS] = m1_success;
        stats_arr[host_stat_index + ATHSTAT_M3_SUCCESS] = m3_success;
        
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"stat count %d\n", stat_idx);
}

void get_value_stat_3(char *folder_name, int curr_radio_index)
{
    char echo_path[FILE_PATH_LEN];
    char read_path[FILE_PATH_LEN];
    FILE *echo_file = NULL;
    FILE *read_file = NULL;
    int stat3_len = 26;
    char stat_buf[CMD_LEN];
    float hw_res[stat3_len];
    int hw_idx = 0;
    int cur_hw_id = 100;
    int host_stat_index = curr_radio_index * CRITICAL_STAT_LEN;

    snprintf(echo_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_echo);
    snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_read);

    char echo_cmd[CMD_LEN];
    snprintf(echo_cmd, sizeof(echo_cmd), "echo 3 > %s", echo_path);
    echo_file = popen(echo_cmd, "w");
    if (echo_file == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run echo command: %s\n", echo_cmd);
        return;
    }
    pclose(echo_file);

    read_file = fopen(read_path, "r");
    if (read_file == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not open read file: %s\n", read_path);
        return;
    }
    while(fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
        if(strstr(stat_buf, "hwq_id = 0")){
            cur_hw_id = 0;
        }
        if(strstr(stat_buf, "hwq_id = 4")){
            cur_hw_id = 4;
        }
        if((cur_hw_id == 4 || cur_hw_id == 0) &&
            strstr(stat_buf, "cmd_result")){
            for(int i = 0; i < 13; i++){
                char pattern[10];
                snprintf(pattern, 10, "%d:", i);
                char *hw= strstr(stat_buf, pattern);
                hw_res[hw_idx++] = atoi(hw + strlen(pattern));
                
                    log_message(LOG_LEVEL_AD_LIB_DEBUG,"hw_res %d: %f\n", i, hw_res[hw_idx - 1]);
                
                if(hw_idx == stat3_len){
                    int j;
                    for(j = 0; j < stat3_len; j++) {
                        stats_arr[host_stat_index + ATHSTAT_CMD_RESULT_MAC0_HWQ0_TYPE0 + j] = hw_res[j];
                    }
                    
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"stat count %d\n", stat_idx);
                    fclose(read_file);
                    return;
                }
            }
            cur_hw_id = 100;
        }
    }
    fclose(read_file);
}

void get_value_stat_48(char *folder_name, int curr_radio_index)
{
    char echo_path[FILE_PATH_LEN];
    char read_path[FILE_PATH_LEN];
    FILE *echo_file = NULL;
    FILE *read_file = NULL;
    char stat_buf[CMD_LEN];
    float type_0 = 0;
    float type_2 = 0;
    float type_4 = 0;
    float type_11 = 0;
    float type_12 = 0;
    float tx_mgmt_1 = 0;
    float tx_mgmt_3 = 0;
    float tx_mgmt_5 = 0;
    float tx_mgmt_10 = 0;
    float tx_mgmt_11 = 0;
    float tx_mgmt_12 = 0;
    int host_stat_index = curr_radio_index * CRITICAL_STAT_LEN;

    snprintf(echo_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_echo);
    snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_read);

    char echo_cmd[CMD_LEN];
    snprintf(echo_cmd, sizeof(echo_cmd), "echo 48 > %s", echo_path);
    echo_file = popen(echo_cmd, "w");
    if (echo_file == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run echo command: %s\n", echo_cmd);
        return;
    }
    pclose(echo_file);

    read_file = fopen(read_path, "r");
    if(read_file == NULL){
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Could not open read file: %s\n", read_path);
        return;
    }
    while(fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
        if(strstr(stat_buf, "fw_rx_mgmt_subtype")){
            char *rx_0 = strstr(stat_buf,"0:");
            type_0 = atoi(&rx_0[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"rx type 0 %f\n", type_0);
            
            char *rx_2 = strstr(stat_buf,"2:");
            type_2 = atoi(&rx_2[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"rx type 2 %f\n", type_2);
            
            char *rx_4 = strstr(stat_buf,"4:");
            type_4 = atoi(&rx_4[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"rx type 4 %f\n", type_4);
            
            char *rx_11 = strstr(stat_buf,"11:");
            type_11 = atoi(&rx_11[3]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"rx type 11 %f\n", type_11);
            
            char *rx_12 = strstr(stat_buf,"12:");
            type_12 = atoi(&rx_12[3]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"rx type 12 %f\n", type_12);
            
        }else if(strstr(stat_buf, "fw_tx_mgmt_subtype")) {
            char *tx_1 = strstr(stat_buf,"1:");
            tx_mgmt_1 = atoi(&tx_1[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"tx type 1 %f\n", tx_mgmt_1);
            
            char *tx_2 = strstr(stat_buf,"3:");
            tx_mgmt_3 = atoi(&tx_2[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"tx type 3 %f\n", tx_mgmt_3);
            
            char *tx_5 = strstr(stat_buf,"5:");
            tx_mgmt_5 = atoi(&tx_5[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"tx type 5 %f\n", tx_mgmt_5);
            
            char *tx_10 = strstr(stat_buf,"10:");
            tx_mgmt_10 = atoi(&tx_10[3]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"tx type 10 %f\n", tx_mgmt_10);
            
            char *tx_11 = strstr(stat_buf,"11:");
            tx_mgmt_11 = atoi(&tx_11[3]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"tx type 11 %f\n", tx_mgmt_11);
            
            char *tx_12 = strstr(stat_buf,"12:");
            tx_mgmt_12 = atoi(&tx_12[3]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"tx type 12 %f\n", tx_mgmt_12);
            
        }
    }
    fclose(read_file);
    stats_arr[host_stat_index + ATHSTAT_FW_RX_MGMT_SUBTYPE_TYPE0] = type_0;
    stats_arr[host_stat_index + ATHSTAT_FW_RX_MGMT_SUBTYPE_TYPE2] = type_2;
    stats_arr[host_stat_index + ATHSTAT_FW_RX_MGMT_SUBTYPE_TYPE4] = type_4;
    stats_arr[host_stat_index + ATHSTAT_FW_RX_MGMT_SUBTYPE_TYPE11] = type_11;
    stats_arr[host_stat_index + ATHSTAT_FW_RX_MGMT_SUBTYPE_TYPE12] = type_12;
    stats_arr[host_stat_index + ATHSTAT_FW_TX_MGMT_SUBTYPE_TX_MGMT_1] = tx_mgmt_1;
    stats_arr[host_stat_index + ATHSTAT_FW_TX_MGMT_SUBTYPE_TX_MGMT_3] = tx_mgmt_3;
    stats_arr[host_stat_index + ATHSTAT_FW_TX_MGMT_SUBTYPE_TX_MGMT_5] = tx_mgmt_5;
    stats_arr[host_stat_index + ATHSTAT_FW_TX_MGMT_SUBTYPE_TX_MGMT_10] = tx_mgmt_10;
    stats_arr[host_stat_index + ATHSTAT_FW_TX_MGMT_SUBTYPE_TX_MGMT_11] = tx_mgmt_11;
    stats_arr[host_stat_index + ATHSTAT_FW_TX_MGMT_SUBTYPE_TX_MGMT_12] = tx_mgmt_12;
    
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"stat count %d\n", stat_idx);
}

void get_ath_host_stats(char *folder_name, int curr_radio_index)
{
    char read_path[FILE_PATH_LEN];
    FILE *read_file = NULL;
    int host_stat_index = curr_radio_index * CRITICAL_STAT_LEN;
    int cli_idx = host_stat_index + ATHSTAT_TOTAL_NUMBER_OF_CONNECTED_CLIENTS;
    char stat_buf[CMD_LEN];
    float txmg = 0;
    float rxmg = 0;
    float clients = 0;

    snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_host_read);

    read_file = fopen(read_path, "r");
    if(read_file == NULL){
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Could not open read file: %s\n", read_path);
        return;
    }
    while(fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
        if(strstr(stat_buf, "Total TX Mgmt frames")){
            char *txmg_str = strstr(stat_buf,"=");
            txmg = atoi(&txmg_str[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"txmg %f\n", txmg);
            
        } else if(strstr(stat_buf, "Total RX Mgmt frames")){
            char *rxmg_str = strstr(stat_buf,"=");
            rxmg = atoi(&rxmg_str[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"rxmg %f\n", rxmg);
            
        } else if(strstr(stat_buf, "Number of connected clients")){
            char *clients_str = strstr(stat_buf,"=");
            clients = atoi(&clients_str[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"clients %f\n", clients);
            
        }
    }
    stats_arr[host_stat_index + ATHSTAT_TX_MANAGEMENT] = txmg;
    stats_arr[host_stat_index + ATHSTAT_RX_MANAGEMENT] = rxmg;
    stats_arr[cli_idx] = clients;
    
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"stat count %d\n", stat_idx);
    fclose(read_file);
}

void get_value_stat_10(char *folder_name, int curr_radio_index)
{
    char echo_path[FILE_PATH_LEN];
    char read_path[FILE_PATH_LEN];
    FILE *echo_file = NULL;
    FILE *read_file = NULL;

    char stat_buf[CMD_LEN];
    int rssi_mgmt = 0;
    int rssi_data = 0;
    int rssi_comb = 0;
    int rssi_in_dbm = 0;
    int host_stat_index = curr_radio_index * CRITICAL_STAT_LEN;

    snprintf(echo_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_echo);
    snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_read);

    char echo_cmd[CMD_LEN];
    snprintf(echo_cmd, sizeof(echo_cmd), "echo 10 > %s", echo_path);
    echo_file = popen(echo_cmd, "w");
    if (echo_file == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run echo command: %s\n", echo_cmd);
        return;
    }
    pclose(echo_file);

    read_file = fopen(read_path, "r");
    if (read_file == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not open read file: %s\n", read_path);
        return;
    }
    while (fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
        if (strstr(stat_buf, "rssi_mgmt =")) {
            char *rssi_mgmt_str = strstr(stat_buf, "=");
            rssi_mgmt = atoi(&rssi_mgmt_str[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "rssi_mgmt: %d\n", rssi_mgmt);
            
        } else if (strstr(stat_buf, "rssi_data =")) {
            char *rssi_data_str = strstr(stat_buf, "=");
            rssi_data = atoi(&rssi_data_str[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "rssi_data: %d\n", rssi_data);
            
        } else if (strstr(stat_buf, "rssi_comb =")) {
            char *rssi_comb_str = strstr(stat_buf, "=");
            rssi_comb = atoi(&rssi_comb_str[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "rssi_comb: %d\n", rssi_comb);
            
        } else if (strstr(stat_buf, "rssi_in_dbm =")) {
            char *rssi_dbm_str = strstr(stat_buf, "=");
            rssi_in_dbm = atoi(&rssi_dbm_str[2]);
            
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "rssi_in_dbm: %d\n", rssi_in_dbm);
            
        }
    }
    fclose(read_file);

    stats_arr[host_stat_index + ATHSTAT_RSSI_MGMT] = rssi_mgmt;
    stats_arr[host_stat_index + ATHSTAT_RSSI_DATA] = rssi_data;
    stats_arr[host_stat_index + ATHSTAT_RSSI_COMB] = rssi_comb;
    stats_arr[host_stat_index + ATHSTAT_RSSI_IN_DBM] = rssi_in_dbm;
    
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "stat count %d\n", stat_idx);
}

int get_radio_center_freq(const char *folder_name) {
    char echo_path[FILE_PATH_LEN];
    char read_path[FILE_PATH_LEN];
    FILE *echo_file = NULL;
    FILE *read_file = NULL;
    char stat_buf[CMD_LEN];
    int freq_val = 0;

    snprintf(echo_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_echo);
    snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, folder_name, suffix_read);

    char echo_cmd[CMD_LEN];
    snprintf(echo_cmd, sizeof(echo_cmd), "echo 37 > %s", echo_path);
    echo_file = popen(echo_cmd, "w");
    if (echo_file == NULL) return 0;
    pclose(echo_file);

    read_file = fopen(read_path, "r");
    if(read_file == NULL) return 0;
    while(fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
        if(strstr(stat_buf, "operating center freq")){
            char *center_freq = strstr(stat_buf,"=");
            freq_val = atoi(&center_freq[2]);
            break;
        }
    }
    fclose(read_file);
    return freq_val;
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


void get_ath_stats()
{
    DIR *dir = opendir(stat_folder_prefix);
    if (dir == NULL) {
        perror("opendir failed");
        return;
    }
    
    struct dirent *entry;
    int count = 0;

    int active_freqs[MAX_RADIO_FREQS];
    int active_count = parse_center_freqs(active_freqs, MAX_RADIO_FREQS);
    
    char *radio_names[MAX_RADIOS];

    while ((entry = readdir(dir)) != NULL) {
        if ((strstr(entry->d_name, "pci") != NULL) || (strstr(entry->d_name, "ahb") != NULL)) {
            int freq = get_radio_center_freq(entry->d_name); // returns MHz
            int found = 0;
            for (int j = 0; j < active_count; j++) {
                if (freq == active_freqs[j]) {
                    found = 1;
                    break;
                }
            }
            if (found) {
                radio_names[count] = strdup(entry->d_name);
                count++;
            } else {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Skipping %s (freq %d not active)\n", entry->d_name, freq);
            }
        }
    }
    closedir(dir);
    
    ath_radios_count = count;

    int stats_arr_len = CRITICAL_STAT_LEN * ath_radios_count;
    int total_len  = stats_arr_len * sizeof(float);
    if(total_len == 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"total len: %d \n", total_len);
        return;
    }

    bands_arr = (int *) malloc(MAX_RADIOS * sizeof(int));
    band_idx = 0;
    stats_arr = (float *) malloc(total_len);
    memset(stats_arr, 0, total_len);
    
    for (int i = 0; i < ath_radios_count; i++) {
        get_ath_host_stats(radio_names[i], i);
        get_value_stat_3(radio_names[i], i);
        get_value_stat_1(radio_names[i], i);
        get_value_stat_48(radio_names[i], i);
        get_value_stat_8(radio_names[i], i);
        get_value_stat_37(radio_names[i], i);
        get_value_stat_10(radio_names[i], i);
        free(radio_names[i]);
    }

    uint16_t buf_len = sizeof(struct meta_data) + total_len + 2 * sizeof(char) + sizeof(int) * ath_radios_count;
    uint8_t* stats_ptr = (uint8_t*)calloc(buf_len, sizeof(uint8_t ));

    struct meta_data* meta_ptr = (struct meta_data*)stats_ptr;

    meta_ptr->srcAppId = APPID_TELEMETRY_SERV_APP;
    meta_ptr->dstAppId = APPID_ANAMOLY_DETECTION;
    meta_ptr->channelNum = INPUT_PARAMS;
    meta_ptr->MSGType = MSG_TYPE_DATA;

    char *type = (char *) ((char*) stats_ptr + sizeof( struct meta_data));
    *type = BAND_TLV;
    char *len = (char *) ((char*) stats_ptr + sizeof( struct meta_data) + sizeof(char));

    *len = 2 * sizeof(char) + sizeof(int) * ath_radios_count;

    float *temp = (float *) ((uint8_t *) stats_ptr + sizeof( struct meta_data) + *len);

    for(i = 0; i < stats_arr_len; i++){
	
        	log_message(LOG_LEVEL_AD_LIB_DEBUG,"AD_lib==%d:%f==\t", i , stats_arr[i]);
	
        temp[i] = stats_arr[i];
    }
    char* band = (char *) ((char*) stats_ptr + sizeof( struct meta_data) + 2 * sizeof(char));
    memcpy(band, bands_arr, sizeof(int) * ath_radios_count);
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Buf_len: %d\n", buf_len);
    local_callbacks.app_handler_send((char*)stats_ptr, buf_len);
    free(stats_arr);
    free(bands_arr);
    return;

}

/*get all the radios on the AP*/
void init_aps_and_radios() {

    char command[TOP_CMD_LEN]={};
    char top_output[TOP_OUTPUT_LEN]= {};
    snprintf(command,TOP_CMD_LEN-1,"ifconfig | grep -e wifi");
    FILE *fp = popen(command, "r");
    if(!fp){
      perror("popen failed");
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

/*
 * htt_print_tx_hwq_cmd_result_stats_tlv_v: display htt_tx_hwq_cmd_result_stats_tlv_v
 * @tag_buf: buffer containing the tlv htt_tx_hwq_cmd_result_stats_tlv_v
 * Only the data for hwq_id=0 is sent to the Data Logger
 * return:void
 */
static inline void htt_print_tx_hwq_cmd_result_stats_tlv_v(void *tag_buf)
{
    uint8_t  i;
    int itr = 0;
    htt_tx_hwq_cmd_result_stats_tlv_v *htt_stats_buf =
        (htt_tx_hwq_cmd_result_stats_tlv_v *)tag_buf;
    itr  = stat_idx / CRITICAL_STAT_LEN;
    if(hw_id == 0) {
	stat_idx = 2;
        stat_idx = (itr * CRITICAL_STAT_LEN) + HW_ID_0_IDX;
    }
    else if(hw_id == 4) {
        stat_idx = 15;
	stat_idx = (itr * CRITICAL_STAT_LEN) + HW_ID_4_IDX;
    }
    else
	return;
    uint32_t *tag = (uint32_t *)tag_buf;
    int tag_len = (HTT_STATS_TLV_LENGTH_GET((uint32_t)*tag) >> 2);
    /*Send stats only for the hwq_id=0, i.e. the first response*/
    
	log_message(LOG_LEVEL_AD_LIB_DEBUG,"hwq_id %d start idx %d: \n", hw_id, stat_idx);
    
        for (i = 0; i < tag_len; i++) {
		stats_arr[stat_idx++] =  htt_stats_buf->cmd_result[i];
	    }
}

/*
 * htt_print_tx_hwq_stats_cmn_tlv: display htt_tx_hwq_stats_cmn_tlv
 * @tag_buf: buffer containing the tlv htt_tx_hwq_stats_cmn_tlv
 *
 * return:void
 */
static inline void htt_print_tx_hwq_stats_cmn_tlv(void *tag_buf)
{
    htt_tx_hwq_stats_cmn_tlv *htt_stats_buf =
        (htt_tx_hwq_stats_cmn_tlv *)tag_buf;
	uint8_t hwq_id = (htt_stats_buf->mac_id__hwq_id__word & 0xFF00) >> 8;
	hw_id = hwq_id;
	if (hwq_id != 0){
	        return;
    }
}

static void htt_print_tx_pdev_stats_cmn_tlv(A_UINT32 *tag_buf)
{
    htt_tx_pdev_stats_cmn_tlv *htt_stats_buf =
        (htt_tx_pdev_stats_cmn_tlv *)tag_buf;
   int itr = 0;
   itr  = stat_idx / CRITICAL_STAT_LEN;
   stat_idx = (itr * CRITICAL_STAT_LEN) + PPDU_OK_IDX;
   stats_arr[stat_idx++] = htt_stats_buf->ppdu_ok;
   stats_arr[stat_idx++] = htt_stats_buf->tx_xretry;
   return;
}

static void htt_print_odd_pdev_mandatory_tlv(void *tag_buf)
{
    htt_odd_mandatory_pdev_stats_tlv *htt_stats_buf =
        (htt_odd_mandatory_pdev_stats_tlv *) tag_buf;
    uint8_t  i;
    uint16_t index = 0;
    int itr = 0;
    char   str_buf[HTT_MAX_STRING_LEN] = {0};

    for (i = 0; i < HTT_STATS_SUBTYPE_MAX; i++) {
        index += snprintf(&str_buf[index],
            HTT_MAX_STRING_LEN - index,
            " %u:%u,", i,
            htt_stats_buf->fw_rx_mgmt_subtype[i]);
    }
    itr  = stat_idx / CRITICAL_STAT_LEN;
    stat_idx = (itr * CRITICAL_STAT_LEN) + FW_MGMT_TX_IDX;
    
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "fw_rx_mgmt_subtype = %s idx %d\n", str_buf, stat_idx);
     
     stats_arr[stat_idx++] =  htt_stats_buf->fw_rx_mgmt_subtype[0];
     stats_arr[stat_idx++] =  htt_stats_buf->fw_rx_mgmt_subtype[2];
     stats_arr[stat_idx++] =  htt_stats_buf->fw_rx_mgmt_subtype[4];
     stats_arr[stat_idx++] =  htt_stats_buf->fw_rx_mgmt_subtype[11];
     stats_arr[stat_idx++] =  htt_stats_buf->fw_rx_mgmt_subtype[12];

    index = 0;
    memset(str_buf, 0x0, HTT_MAX_STRING_LEN);

    for (i = 0; i < HTT_STATS_SUBTYPE_MAX; i++) {
        index += snprintf(&str_buf[index],
            HTT_MAX_STRING_LEN - index,
            " %u:%u,", i,
            htt_stats_buf->fw_tx_mgmt_subtype[i]);
    }
    
	    log_message(LOG_LEVEL_AD_LIB_DEBUG, "fw_tx_mgmt_subtype = %s start idx %d\n", str_buf, stat_idx);
    
    stats_arr[stat_idx++] =  htt_stats_buf->fw_tx_mgmt_subtype[1];
    stats_arr[stat_idx++] =  htt_stats_buf->fw_tx_mgmt_subtype[2];
    stats_arr[stat_idx++] =  htt_stats_buf->fw_tx_mgmt_subtype[5];
    stats_arr[stat_idx++] =  htt_stats_buf->fw_tx_mgmt_subtype[10];
    stats_arr[stat_idx++] =  htt_stats_buf->fw_tx_mgmt_subtype[11];
    stats_arr[stat_idx++] =  htt_stats_buf->fw_tx_mgmt_subtype[12];
}

/*
 * htt_print_tx_de_eapol_packets_stats_tlv: display htt_tx_de_eapol_packets_stats
 * @tag_buf: buffer containing the tlv htt_tx_de_eapol_packets_stats_tlv
 *
 * return:void
 */
static void htt_print_tx_de_eapol_packets_stats_tlv(void *tag_buf)
{
    htt_tx_de_eapol_packets_stats_tlv *htt_stats_buf =
        (htt_tx_de_eapol_packets_stats_tlv *)tag_buf;
    
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"M3 start index %d, %d - %d -%d - %d\n", stat_idx, htt_stats_buf->m1_packets, htt_stats_buf->m3_packets, htt_stats_buf->m1_success, htt_stats_buf->m3_success);
    
    stats_arr[stat_idx++] = htt_stats_buf->m1_packets;
    stats_arr[stat_idx++] = htt_stats_buf->m3_packets;
    stats_arr[stat_idx++] = htt_stats_buf->m1_success;
    stats_arr[stat_idx++] = htt_stats_buf->m3_success;
    
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"M3 end index %d\n", stat_idx -1);
    
}

static void htt_print_pdev_cca_stats_hist_tlv(void *tag_buf)
{
    htt_pdev_cca_stats_hist_v1_tlv *htt_stats_buf =
        (htt_pdev_cca_stats_hist_v1_tlv *)tag_buf;
    cca_num = htt_stats_buf->num_records;
}

static void htt_print_phy_reset_stats_tlv(void *tag_buf)
{
    htt_phy_reset_stats_tlv *htt_stats_phy_reset_stats_buf =
                    (htt_phy_reset_stats_tlv *) tag_buf;
    bands_arr[band_idx++] = htt_stats_phy_reset_stats_buf->chan_band_center_freq1 / 1000;
    
	    log_message(LOG_LEVEL_AD_LIB_DEBUG,"BAND --------- %d fREQ %d\n", bands_arr[band_idx - 1], htt_stats_phy_reset_stats_buf->chan_band_center_freq1);
    
}
/*
 * htt_print_pdev_stats_cca_counters_tlv: display htt_pdev_stats_cca_counters_tlv
 * @tag_buf: buffer containing the tlv htt_pdev_stats_cca_counters_tlv
 *
 * return:void
 */
static void htt_print_pdev_stats_cca_counters_tlv(void *tag_buf)
{
    htt_pdev_stats_cca_counters_tlv *htt_stats_buf =
        	(htt_pdev_stats_cca_counters_tlv *)tag_buf;
    if(cca_num != 1)
        return;

    /* stat_idx is currently somewhere inside the current radio's segment.
       Anchor to that radio's base so the 4 CCA fields land at fixed slots
       50..53 regardless of TLV arrival order within the per-radio loop. */
    int radio_base = (stat_idx / CRITICAL_STAT_LEN) * CRITICAL_STAT_LEN;
    stats_arr[radio_base + ATHSTAT_CCA_RX_CLEAR]    = htt_stats_buf->rx_clear_usec;     /* total medium occupied */
    stats_arr[radio_base + ATHSTAT_CCA_TX_FRAME]    = htt_stats_buf->tx_frame_usec;     /* IBSS tx */
    stats_arr[radio_base + ATHSTAT_CCA_MY_RX_FRAME] = htt_stats_buf->my_rx_frame_usec;  /* IBSS rx */
    stats_arr[radio_base + ATHSTAT_CCA_RX_FRAME]    = htt_stats_buf->rx_frame_usec;     /* IBSS rx + OBSS rx */
}

static void htt_print_rx_pdev_rate_stats_tlv(void *tag_buf)
{
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"htt_print_rx_pdev_rate_stats_tlv\n");
    htt_rx_pdev_rate_stats_tlv *htt_stats_buf =
        (htt_rx_pdev_rate_stats_tlv *)tag_buf;
    stat_idx++;
    stats_arr[stat_idx++] = htt_stats_buf->rssi_mgmt;
    stats_arr[stat_idx++] = htt_stats_buf->rssi_data;
    stats_arr[stat_idx++] = htt_stats_buf->rssi_comb;
    stats_arr[stat_idx++] = htt_stats_buf->rssi_in_dbm;
}

void parse_wifistats_tlv(void *ctx)
{
    uint32_t tlv_word;
    tlv_word = *((uint32_t *)ctx);
    htt_tlv_tag_t tlv_type  = 0xff;
    tlv_type = HTT_STATS_TLV_TAG_GET(tlv_word);
    if(HTT_STATS_TX_DE_EAPOL_PACKETS_TAG == tlv_type){
	htt_print_tx_de_eapol_packets_stats_tlv(ctx);
    }
    else if(HTT_STATS_ODD_PDEV_MANDATORY_TAG == tlv_type){
	htt_print_odd_pdev_mandatory_tlv(ctx);
    }
    else if(HTT_STATS_TX_PDEV_CMN_TAG == tlv_type) {
        htt_print_tx_pdev_stats_cmn_tlv(ctx);
    }
    else if(HTT_STATS_TX_HWQ_CMN_TAG == tlv_type) {
        htt_print_tx_hwq_stats_cmn_tlv(ctx);
    }
    else if(HTT_STATS_TX_HWQ_CMD_RESULT_TAG == tlv_type) {
        htt_print_tx_hwq_cmd_result_stats_tlv_v(ctx);
    }
    else if((HTT_STATS_PDEV_CCA_STAT_CUMULATIVE_TAG == tlv_type) ||
	(HTT_STATS_PDEV_CCA_100MSEC_HIST_TAG == tlv_type) ||
	(HTT_STATS_PDEV_CCA_1SEC_HIST_TAG == tlv_type)) {
	htt_print_pdev_cca_stats_hist_tlv(ctx);
    }
    else if(HTT_STATS_PDEV_CCA_COUNTERS_TAG == tlv_type) {
        htt_print_pdev_stats_cca_counters_tlv(ctx);
    } else if(HTT_STATS_PHY_RESET_STATS_TAG == tlv_type) {
         htt_print_phy_reset_stats_tlv(ctx);
    } else if(HTT_STATS_RX_PDEV_RATE_STATS_TAG == tlv_type) {
         htt_print_rx_pdev_rate_stats_tlv(ctx);
    }
}

static void wifistats_callback_token(void *ctx, void *token) {
    
	    log_message(LOG_LEVEL_AD_LIB_DEBUG,"wifistats_callback_token\n");
    
    void *next_ptr = ctx;
    while(next_ptr != NULL) {
        parse_wifistats_tlv(next_ptr);
        next_ptr = wifistats_get_next_tlv(ctx);
    }
    
	    log_message(LOG_LEVEL_AD_LIB_DEBUG,"wifistats_callback_token null\n");
    
    if(ctx != NULL)
	wifistats_free(ctx);
    done = 1;
}


void get_wifi_stats()
{
    int radio_idx = 0;
    init_aps_and_radios();
    total_clients = 0;
    /* +1 for the total no of clients */
    int total_len  = ((CRITICAL_STAT_LEN * radios_count)) * sizeof(float);
    if(total_len == 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"total len: %d \n", total_len);
        return;
    }
    bands_arr = (int *) malloc(MAX_RADIOS * sizeof(int));
    band_idx = 0;
    stats_arr = (float *) malloc(total_len);
    memset(stats_arr, 0, total_len);
    int i, j = 0;

    int (*wifistats_get) (void *col, int argc, char *argv[], void (*callback)(void *data, void *token), void *token);
    void* (*collector_start)(void);
    void (*collector_end)(void *);
    /*Load all the required symbols*/
   wifistats_get = (int (*)(void *col, int argc, char *argv[], void (*callback)(void *data, void *token), void *token))dlsym(wifistats_handle,"wifistats_get_with_text_args_token");
   if(wifistats_get == NULL){
	log_message(ERROR, "error getting wifistats_get_with_text_args_token from lib!! %d, %s", errno, dlerror());
	return;
   }
   collector_start = dlsym(qca_tools_handle,"collector_start");
   if(collector_start == NULL){
        log_message(ERROR, "error getting collector_start from lib!! %d, %s", errno, dlerror());
        return;
   }
   collector_end = dlsym(qca_tools_handle,"collector_end");
   if(collector_end == NULL){
        log_message(ERROR, "error getting collector_end from lib!! %d, %s", errno, dlerror());
        return;
   }
   /*Start collector thread*/
   col = (void*) collector_start();
   for(j = 0; j < radios_count; j++){
      radio_idx = j;
      get_host_stats(j);
   }
   /*Get stats for all the radios*/
   for(j = 0; j < radios_count; j++){
      radio_idx = j;
        stat_idx = (radio_idx * CRITICAL_STAT_LEN) + 2;
	for(i = 0; i < CRITICAL_STAT_COUNT; i++) {
    		int argc = 0;
    		char *argv[20];
    		char stat_type[5];
	    	int stat_id = critical_stat[i];
		snprintf(stat_type, 5, "%d", stat_id);
		argv[argc++] = "wifistats";
		
			log_message(LOG_LEVEL_AD_LIB_DEBUG,"radio: %s stat type: %s\n", radios[j], stat_type);
		
	    argv[argc++] = radios[j];
	    argv[argc++] = stat_type;
	    wifistats_get(col, argc, argv, wifistats_callback_token, (void*)(uintptr_t) radio_idx);
	    while(done != 1)
		usleep(100);
	    done = 0;
	 }
    }
    
	    log_message(LOG_LEVEL_AD_LIB_DEBUG,"+++stats len %d stat idx %d\n", total_len, stat_idx);
    
    
    uint16_t buf_len = sizeof(struct meta_data) + total_len + 2 * sizeof(char) + sizeof(int) * radios_count;
    uint8_t* stats_ptr = (uint8_t*)calloc(buf_len, sizeof(uint8_t )); 
    
    struct meta_data* meta_ptr = (struct meta_data*)stats_ptr;
   
    meta_ptr->srcAppId = APPID_TELEMETRY_SERV_APP;
    meta_ptr->dstAppId = APPID_ANAMOLY_DETECTION;
    meta_ptr->channelNum = INPUT_PARAMS;
    meta_ptr->MSGType = MSG_TYPE_DATA;
    
    char *type = (char *) ((char*) stats_ptr + sizeof( struct meta_data));
    *type = BAND_TLV; 
    char *len = (char *) ((char*) stats_ptr + sizeof( struct meta_data) + sizeof(char));

    *len = 2 * sizeof(char) + sizeof(int) * radios_count;

    float *temp = (float *) ((uint8_t *) stats_ptr + sizeof( struct meta_data) + *len);
 
    for(i = 0; i < stat_idx; i++){
	
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"AD_lib==%d:%f==\t", i , stats_arr[i]);
	
	temp[i] = stats_arr[i];
    }
    char* band = (char *) ((char*) stats_ptr + sizeof( struct meta_data) + 2 * sizeof(char));
    memcpy(band, bands_arr, sizeof(int) * radios_count);
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Buf_len: %d\n", buf_len);
    local_callbacks.app_handler_send((char*)stats_ptr, buf_len);
    free(stats_arr);
    free(bands_arr);
    collector_end(col);
    return;
}

void app_handler_rcv(char* payload, size_t payload_len) 
{
	FILE *conf_fp;
        char buf[256];
        conf_fp = fopen(WIFI_CONF, "r");
        if (conf_fp == NULL) {
                printf("Error opening WiFi conf file\n");
                return;
        }
        while (fgets(buf, 256, conf_fp)) {
                if(strstr(buf, ATH_CONF_STR) != NULL) {
                        if(conf_fp) fclose(conf_fp);
                        get_ath_stats();
                        return;
                }
        }
	if(conf_fp) fclose(conf_fp);
	get_wifi_stats();
}

void get_host_stats(int radio_idx)
{
	int host_stat_idx = (radio_idx * CRITICAL_STAT_LEN);
	int cli_idx = host_stat_idx + ATHSTAT_TOTAL_NUMBER_OF_CONNECTED_CLIENTS;
	
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"get_host_stats radio idx %d stats idx: %d radio: %s\n", radio_idx, host_stat_idx, radios[radio_idx]);
	
	char cmd[CMD_LEN];
	char *tele_cmd = "wifitelemetry --basic --radio -c --ifname=";
	strlcpy(cmd, tele_cmd, CMD_LEN);
	strlcat(cmd, radios[radio_idx], CMD_LEN);
	FILE *host_cmd;
	char stat_buf[CMD_LEN];
	int tx_mgt_val, rx_mgt_val, client_val = 0;
	
	host_cmd = popen(cmd, "r");
	if(host_cmd == NULL){
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"could Not run command\n");
		return;
	}
	while(fgets(stat_buf, sizeof(stat_buf), host_cmd) != NULL) {
		if(strstr(stat_buf, "Tx Management")){
			char *tx_mgt = strstr(stat_buf,"=");
			tx_mgt_val = atoi(&tx_mgt[2]);
			
				printf("%d\n",tx_mgt_val);
			
			
		} else if(strstr(stat_buf, "Number of connected clients")){
                        char *cli_str = strstr(stat_buf,"=");
                        client_val = atoi(&cli_str[2]);
			
	                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"%d\n", client_val);
			

                }else if(strstr(stat_buf, "Rx Management")){
                        char *rx_mgt = strstr(stat_buf,"=");
                        rx_mgt_val = atoi(&rx_mgt[2]);
			
                        	log_message(LOG_LEVEL_AD_LIB_DEBUG,"%d\n",rx_mgt_val);
			

                }
	}
	stats_arr[cli_idx] = client_val;
        stats_arr[host_stat_idx++] = rx_mgt_val;
        stats_arr[host_stat_idx++] = tx_mgt_val;
	if(host_cmd) pclose(host_cmd);
}

// Function to load all required libraries
int ad_load_wifi_libraries() {
    // Check if ath build or prop:
    FILE *conf_fp;
    char buf[256];
    conf_fp = fopen(WIFI_CONF, "r");
    if (conf_fp == NULL) {
            printf("Error opening WiFi conf file\n");
            return;
    }
    while (fgets(buf, 256, conf_fp)) {
            if(strstr(buf, ATH_CONF_STR) != NULL) {
                    fclose(conf_fp);
                    return;
            }
    }
    nl3_handle = dlopen("/usr/lib/libnl-3.so.200", RTLD_LAZY | RTLD_GLOBAL);
    if (nl3_handle == NULL) {
        fprintf(stderr, "Failed to open libnl-3.so.200, errno: %d, error: %s\n", errno, dlerror());
        return -1;
    }

    gennl_handle = dlopen("/usr/lib/libnl-genl-3.so.200", RTLD_LAZY | RTLD_GLOBAL);
    if (gennl_handle == NULL) {
        fprintf(stderr, "Failed to open libgennl.so, errno: %d, error: %s\n", errno, dlerror());
        return -1;
    }

    qcanl_handle = dlopen("/usr/lib/libqca_nl80211_wrapper.so", RTLD_LAZY | RTLD_GLOBAL);
    if (qcanl_handle == NULL) {
        fprintf(stderr, "Failed to open libqcanl.so, errno: %d, error: %s\n", errno, dlerror());
        return -1;
    }

    qca_tools_handle = dlopen("/usr/lib/libqca_tools.so", RTLD_LAZY | RTLD_GLOBAL);
    if (qca_tools_handle == NULL) {
        fprintf(stderr, "Failed to open libqcatools.so, errno: %d, error: %s\n", errno, dlerror());
        return -1;
    }

    apstats_handle = dlopen("/usr/lib/libapstats.so", RTLD_LAZY | RTLD_GLOBAL);
    if (apstats_handle == NULL) {
        fprintf(stderr, "Failed to open libapstats.so, errno: %d, error: %s\n", errno, dlerror());
        return -1;
    }

    wifistats_handle = dlopen("/usr/lib/libwifistats.so", RTLD_LAZY | RTLD_GLOBAL);
    if (wifistats_handle == NULL) {
        fprintf(stderr, "Failed to open libwifistats.so, errno: %d, error: %s\n", errno, dlerror());
        return -1;
    }

    wlanfw_handle = dlopen("/usr/lib/libwlanfw_htt.so", RTLD_LAZY | RTLD_GLOBAL);
    if (wlanfw_handle == NULL) {
        fprintf(stderr, "Failed to open libwlanfw.so, errno: %d, error: %s\n", errno, dlerror());
        return -1;
    }

    stats_handle = dlopen("/usr/lib/libstats_lib.so", RTLD_LAZY | RTLD_GLOBAL);
    if(stats_handle == NULL){
        log_message(LOG_LEVEL_AD_LIB_ERROR, "Failed to open stats tool library, %d, %s", errno, dlerror());
        return -1;
    }
    return 0;
}

void ad_close_wifi_libraries() {
    if (nl3_handle) {
        if (dlclose(nl3_handle) != 0)
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to close nl3_handle: %s\n", dlerror());
        nl3_handle = NULL;
    }
    
    if (gennl_handle) {
        if (dlclose(gennl_handle) != 0)
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"Failed to close gennl_handle: %s\n", dlerror());
        gennl_handle = NULL;
    }
    
    if (qcanl_handle) {
        if (dlclose(qcanl_handle) != 0)
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"Failed to close qcanl_handle: %s\n", dlerror());
        qcanl_handle = NULL;
    }
    
    if (qca_tools_handle) {
        if (dlclose(qca_tools_handle) != 0)
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"Failed to close qca_tools_handle: %s\n", dlerror());
        qca_tools_handle = NULL;
    }
    
    if (apstats_handle) {
        if (dlclose(apstats_handle) != 0)
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"Failed to close apstats_handle: %s\n", dlerror());
        apstats_handle = NULL;
    }
    
    if (wifistats_handle) {
        if (dlclose(wifistats_handle) != 0)
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"Failed to close wifistats_handle: %s\n", dlerror());
        wifistats_handle = NULL;
    }
    
    if (wlanfw_handle) {
        if (dlclose(wlanfw_handle) != 0)
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"Failed to close wlanfw_handle: %s\n", dlerror());
        wlanfw_handle = NULL;
    }
    
    if (stats_handle) {
        if (dlclose(stats_handle) != 0)
            log_message(LOG_LEVEL_AD_LIB_DEBUG,"Failed to close stats_handle: %s\n", dlerror());
        stats_handle = NULL;
    }
}

void lib_init(TelemetryServiceAPPCallbacks *callbacks) 
{
    log_message(LOG_LEVEL_AD_LIB_INFO, "ad handler:lib_init , setting local_callbacks"); 
    local_callbacks = *callbacks;
    
    if (ad_load_wifi_libraries() != 0) {
        log_message(LOG_LEVEL_AD_LIB_ERROR, "Failed to load required libraries");
    }
}
