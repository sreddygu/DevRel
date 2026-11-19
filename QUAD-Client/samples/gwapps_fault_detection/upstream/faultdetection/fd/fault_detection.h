/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#ifndef FAULT_DETECTION_H
#define FAULT_DETECTION_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <limits.h>
#include <time.h>

// Version and Port Configuration
#define VERSION_NUM_1 1
#define VERSION_NUM_3 3   // GWApps 1.2
#define FD_PORT 9099

// Radio and Interface Configuration
#define MAX_RADIOS 4
#define MAC_ADDRESS_LEN_IN_CHARS 18
#define TOP_OUTPUT_LEN 1024
#define TOP_CMD_LEN 300
#define VAP_RADIO_LEN_MAX 16
#define HTT_MAX_STRING_LEN 1000
#define MAX_INTERFACES 16
#define MAX_RADIO_FREQS 16

// Network Configuration
#define LOCAL_HOST "127.0.0.1"

// Buffer and String Lengths
#define CMD_LEN 1024
#define MAX_LEN 2048
#define MAC_LEN 18
#define INT_STR 5
#define NOTE_LEN 1024
#define LOG_LEN 4096
#define APP_NAME_LEN 50

// String Constants
#define LINK_COLON ":"
#define IFACE_STR "Interface"
#define WLAN_STR "wlan"
#define LINK_STR "link "
#define DIR_CMD "mkdir "
#define WILD "*"
#define DEL_CMD "rm -rf "
#define SPACE " "
#define REDIR " > "
#define UNDR_SCR "_"
#define TXT_EXT ".txt"
#define WMI_STR "--wmi"
#define PKT_CPY "cp /proc/ath_pktlog/"
#define FWD_SLSH "/"
#define WIFI_STR "wifistats"
#define PKT_CMD_1 "pktlogconf -a "
#define PKT_CMD_2 " -elite -s 10000000"
#define PKT_STP "pktlogconf -d "
#define FILE_STR "fd_logs.txt"
#define LOG_CMD "logread > "
#define SYS_LOG_NAME "syslog.txt"
#define SYS_START "/etc/init.d/log start"
#define COL_STR ";"
#define SYS_END "/etc/init.d/log stop"

// Statistics and Model Configuration
#define CRITICAL_STAT_LEN 54
#define ANOMALY_STAT_CNT 16

#define M1_M3_RATE_IDX 14
#define PCT_IDX 2
#define CLIENTS_IDX 45
// #define MAX_ITER 4
#define INPUT_VEC_LEN 46
#define MODEL_VEC_LEN 14
#define MIN_BUFFER 1
#define MAX_BUFFER 10
#define DEFAULT_BUFFER 4
// Anomaly Folder Limits
#define MIN_ANOMALY_FOLDERS_ALL 1
#define MAX_ANOMALY_FOLDERS_LOCAL 16
#define DEFAULT_MAX_ANOMALY_FOLDERS 10
#define DISK_SPACE_THRESHOLD_PERCENT 20.0

// WiFi Configuration
#define WIFI_CONF "/etc/config/wireless"
#define ATH_CONF_STR "config smp_affinity"

// Statistics Indices
#define PPDU_OK_IDX 28
#define TX_XRET_IDX 29
#define HW_0_ST 2
#define HW_0_END 14
#define HW_4_ST 15
#define HW_4_END 27
#define FW_RX_MGMT_IDX 30
#define FW_MGMT_TX_IDX 30
#define HW_ID_0_IDX 2
#define HW_ID_4_IDX 15
#define RX_MG_11 33
#define RX_MG_12 34
#define TX_MG_1  35
#define TX_MG_3  36
#define TX_MG_11 39
#define TX_MG_12 40
#define M1_PACKET_IDX 41
#define M3_PACKET_IDX 42
#define M1_SUCCESS_IDX 43
#define M3_SUCCESS_IDX 44
#define M1_M3_LEN 5
#define RSSI_LEN 4
#define HOST_STAT_CNT 2
#define COL_TIME 10
// #define MAX_ITR 1024
#define RX_TYPE_4 32
#define TX_TYPE_5 37
#define RX_TYPE_12 34
#define TX_TYPE_12 40

// Threshold and Constant Values
#define NFZERO -0.000001
#define PFZERO 0.000001
#define BEACON_FAIL_THRESH 0.2
#define DATA_STALL_THRESHOLD_DEFAULT 0.8f
#define FDOT25 0.25
#define FDOT6 0.6
#define FDOT5 0.5
#define FDOT7 0.7
#define FONE  1

// Normalization and Cloud Configuration
#define NORMALIZE_MAX_LEN 100
#define MAX_PENDING_UPLOADS 10

// Band Configuration
#define BAND_2G 2
#define BAND_5G 5
#define BAND_6G 6

// Model Configuration
#define MODEL_2G "WIN-NW-FD-AE-2G.dlc"
#define MODEL_5G "WIN-NW-FD-AE-5G.dlc"
#define MODEL_6G "WIN-NW-FD-AE-6G.dlc"
#define MODEL_PATH "/usr/sbin/"

// File Paths
#define CONFIG_FILE "/etc/fd/fd.conf"

// Feature ID
#define AD_FID 3026

// Anomaly Types
#define ANOM_BEACON_STUCK 1
#define ANOM_DATA_STALL 2
#define ANOM_DISCONNECT 3
#define ANOM_FAIL_CONNECT 4

// Test Label Constants
#define TEST_LABEL_DATA_STALL "data_stall"
#define TEST_LABEL_BEACON_STUCK "beacon_stuck"
#define TEST_LABEL_CLIENT_DISCONNECT "client_disconnect"
#define TEST_LABEL_FAIL_TO_CONNECT "fail_to_connect"
#define TEST_LABEL_PASS "pass"
#define TEST_NAME_DEFAULT "default_test"

// Enumerations
typedef enum {
    LOG_LEVEL_AD_LIB_DEBUG,
    LOG_LEVEL_AD_LIB_INFO,
    LOG_LEVEL_AD_LIB_WARN,
    LOG_LEVEL_AD_LIB_ERROR
} LogLevel;

typedef enum {
	BAND_TLV = 1
} tlv_type;

// External Variable Declarations
extern const char * stat_name[CRITICAL_STAT_LEN];

// Global variables needed by cia_services.c
extern int g_test_level;
extern char g_test_label[64];
extern char g_test_name[64];
extern float g_last_stats_per_radio[MAX_RADIOS][CRITICAL_STAT_LEN];
extern int g_last_stats_available[MAX_RADIOS];
extern char g_tl2_expected_label[MAX_RADIOS][32];
extern char g_tl2_message_id[MAX_RADIOS][128];
extern int g_tl2_pending[MAX_RADIOS];
extern float *g_prev_itr_by_band[7];
extern int g_prev_cli_by_band[7];
extern int g_tl2_cycle_no;
extern int g_tl2_seen_first_by_band[7];
extern int g_broadcast_test_level;

// Reference wifistat paths (shared between fault_detection.c and preprocess.c)
extern char reference_wifistat_path_2g[CMD_LEN];
extern char reference_wifistat_path_5g[CMD_LEN];
extern char reference_wifistat_path_6g[CMD_LEN];

// Global variables needed by log_capture.c and other modules
extern time_t g_last_send_note_time;
extern int ath_build;
extern char stat_folder_prefix[];
extern int active_freqs[MAX_RADIO_FREQS];
extern int radios_count;
extern char radios[MAX_RADIOS][VAP_RADIO_LEN_MAX];
extern char radio_macs[MAX_RADIOS][MAC_ADDRESS_LEN_IN_CHARS];
extern char log_folder[CMD_LEN];
extern int cur_bands[MAX_RADIOS];
extern int anomaly_stat[ANOMALY_STAT_CNT];
extern char suffix_echo[];
extern char suffix_read[];
extern char log_dir[MAX_LEN];
extern int sys_log_avail;
extern char cur_sys_path[PATH_MAX];
extern int debug_lvl;
extern int save_logs_to_usb;
extern int inf_inter;
extern float data_stall_threshold;
extern int anomaly_count;
extern int max_anomaly_count;
extern int effective_max_anomaly_count;
extern int itr_cnt;
extern int *anomaly_history;
extern int prev_cli_count;
// extern float mse_2g;
// extern float mse_5g;
// extern float mse_6g;
extern int enable_data_stall;
extern int enable_beacon_stuck;
extern int enable_client_disconnect;
extern int enable_fail_to_connect;
extern char *note_value;
extern char note_message[NOTE_LEN];

// Function Declarations
void send_on_channel(int srcApp, int dstApp, int chanNum, int mstType, char *msg, int msgSize);
void send_test_level_broadcast(void);
void send_note(int rad_id, int band, int type);
int get_radio_center_freq(const char *folder_name);
int parse_center_freqs(int *freqs, int max_freqs);
void init_aps_and_radios();
int calculate_rate_of_change(const char *reference_path, const char *current_path, const char *output_path);

#endif // FAULT_DETECTION_H
