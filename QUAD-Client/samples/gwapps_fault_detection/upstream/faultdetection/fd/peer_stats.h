/*
*  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
*  All rights reserved.
*  Confidential and Proprietary - Qualcomm Technologies, Inc.
*/

#ifndef PEER_STATS_H
#define PEER_STATS_H

#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <time.h>

#define MAX_RADIO_FREQS_PEER 16
#define MAX_RADIOS_PEER 5
extern int MAX_PEERS;
#define MAX_NETDEVS_PEER 8
#define MAX_MACS_PER_NETDEV 512
#define MAX_LINKS_PEER 4
#define CMD_LEN_PEER 256
#define MAX_PATH_PEER 256

// Peer classification thresholds
// RSSI thresholds (in dBm)
#define RSSI_EXCELLENT_THRESHOLD -75
#define RSSI_GOOD_THRESHOLD -80
#define RSSI_FAIR_THRESHOLD -85

// PER thresholds (in percentage)
#define PER_EXCELLENT_THRESHOLD 10.0
#define PER_GOOD_THRESHOLD 20.0
#define PER_FAIR_THRESHOLD 30.0

// TX MCS indices
typedef enum {
    TX_MCS_0,
    TX_MCS_1,
    TX_MCS_2,
    TX_MCS_3,
    TX_MCS_4,
    TX_MCS_5,
    TX_MCS_6,
    TX_MCS_7,
    TX_MCS_8,
    TX_MCS_9,
    TX_MCS_10,
    TX_MCS_11,
    TX_MCS_12,
    TX_MCS_13,
    TX_MCS_14,
    TX_MCS_15,
    TX_MCS_MAX
} TxMcsIndex;

// RX MCS indices
typedef enum {
    RX_MCS_0,
    RX_MCS_1,
    RX_MCS_2,
    RX_MCS_3,
    RX_MCS_4,
    RX_MCS_5,
    RX_MCS_6,
    RX_MCS_7,
    RX_MCS_8,
    RX_MCS_9,
    RX_MCS_10,
    RX_MCS_11,
    RX_MCS_12,
    RX_MCS_13,
    RX_MCS_14,
    RX_MCS_15,
    RX_MCS_MAX
} RxMcsIndex;

// TX PPDU BW indices
typedef enum {
    TX_PPDU_BW_0,
    TX_PPDU_BW_1,
    TX_PPDU_BW_2,
    TX_PPDU_BW_3,
    TX_PPDU_BW_4,
    TX_PPDU_BW_MAX
} TxPpduBwIndex;

// RX PPDU BW indices
typedef enum {
    RX_PPDU_BW_0,
    RX_PPDU_BW_1,
    RX_PPDU_BW_2,
    RX_PPDU_BW_3,
    RX_PPDU_BW_4,
    RX_PPDU_BW_MAX
} RxPpduBwIndex;

// Peer status classification
typedef enum {
    PEER_STATUS_EXCELLENT,
    PEER_STATUS_GOOD,
    PEER_STATUS_FAIR,
    PEER_STATUS_POOR,
    PEER_STATUS_UNKNOWN
} PeerStatus;

typedef enum {
    RSSI_STATUS_EXCELLENT,
    RSSI_STATUS_GOOD,
    RSSI_STATUS_FAIR,
    RSSI_STATUS_POOR,
    RSSI_STATUS_UNKNOWN
} RssiStatus;

#define PEER_STATUS_STRING(status) \
    ((status) == PEER_STATUS_EXCELLENT ? "Excellent" : \
     (status) == PEER_STATUS_GOOD ? "Good" : \
     (status) == PEER_STATUS_FAIR ? "Fair" : \
     (status) == PEER_STATUS_POOR ? "Poor" : "Unknown")

#define RSSI_STATUS_STRING(status) \
    ((status) == RSSI_STATUS_EXCELLENT ? "Excellent" : \
     (status) == RSSI_STATUS_GOOD ? "Good" : \
     (status) == RSSI_STATUS_FAIR ? "Fair" : \
     (status) == RSSI_STATUS_POOR ? "Poor" : "Unknown")

typedef struct {
    char mld_mac[18];
    char link_mac[18];
    
    // Individual stats
    int32_t rx_rssi; // it is called last_rssi in the file
    uint64_t tx_ppdu_cnt; // it is called tx_ppdu_cnt in the file
    uint64_t rx_ppdu_cnt; // it is called ppdu_cnt in file

    uint64_t tx_mpdu_try_cnt; // it is called tx_mpdu_try_cnt in the file
    uint64_t tx_removed_mpdu_cnt; // Missing in file
    uint64_t tx_mpdu_success_cnt; // it is called tx_mpdu_success_cnt in the file

    uint64_t rx_mpdu_try_cnt; // it is called rx_mpdu_try_cnt in the file
    uint64_t rx_mpdu_success_cnt; // it is called mpdu_cnt in the file
    
    uint64_t dl_speed; // it is as transmitted_ppdu_bytes in the file
    uint64_t ul_speed; // Missing in the file

    float tx_per;
    float rx_per;
    int associated_channel_number; // Channel number
    RssiStatus rssi_status; // "Good", "Bad", "Excellent" based on thresholds
    uint64_t tx_msdu_count; // Sum of total_processed_msdu_count

    float channel_utilization;
    int association_bandwidth; // Association bandwidth in MHz
    int frequency_band; // Operating frequency in MHz
    
    // Array stats
    uint32_t tx_mcs[TX_MCS_MAX]; // it is called tx_mcs in file
    uint32_t rx_mcs[RX_MCS_MAX]; // it is called rx_mcs in file
    uint32_t tx_ppdu_bw[TX_PPDU_BW_MAX]; // it is called tx_bw in file
    uint32_t rx_ppdu_bw[RX_PPDU_BW_MAX]; // it is called rx_bw in file
    
    PeerStatus peer_status; // Classification of peer quality
} PeerStats;

typedef struct PeerStatsNode {
    PeerStats stats;
    struct PeerStatsNode *next;
} PeerStatsNode;

typedef struct {
    int count;
    PeerStatsNode *head;
    PeerStatsNode *tail;
} AllPeerStats;

typedef enum {
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARN,
    LOG_LEVEL_ERROR
} LogLevelPeer;



int get_all_peer_stats(AllPeerStats *all_stats, const char *filepath);
void classify_peers(AllPeerStats *all_stats);
void print_peer_stats(const AllPeerStats *all_stats);
int write_peer_stats_to_file(const AllPeerStats *all_stats, const char *filepath);
void free_all_peer_stats(AllPeerStats *all_stats);

// Debuggability control functions
void peer_stats_set_debug_file_ptr(FILE **debug_fp_ptr);
void peer_stats_set_debug_file(const char *debug_file_path);
void peer_stats_enable_debug(void);
void peer_stats_disable_debug(void);
int peer_stats_is_debug_active(void);

// Log message function
void log_message_peer(LogLevelPeer level, const char *format, ...);

#endif // PEER_STATS_H
