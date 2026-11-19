/*
*  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
*  All rights reserved.
*  Confidential and Proprietary - Qualcomm Technologies, Inc.
*/
 
#include "peer_stats.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <stdarg.h>
#include <time.h>
#include <ctype.h>
#include <unistd.h>
#include <limits.h>

#define MCS_STR_BUF_SIZE    300
#define BW_STR_BUF_SIZE     200

// Debuggability globals for peer_stats
// Note: peer_stats now uses the shared debug file pointer from fault_detection.c
static volatile int g_debug_active_peer = 0;
static FILE **g_debug_fp_peer_ptr = NULL;  // Pointer to the shared debug file pointer

char stat_folder_prefix_peer[] = "/sys/kernel/debug/ath12k/";
char suffix_echo_peer[] = "/htt_stats_type";
char suffix_read_peer[] = "/htt_stats";
char netdev_folder_location[] = "/sys/kernel/debug/ieee80211/";

void log_message_peer(LogLevelPeer level, const char *format, ...)
{
    static int debug_enabled = -1;
    if (debug_enabled == -1) {
        const char *env = getenv("DEBUG_ENABLED");
        debug_enabled = (env && strcmp(env, "1") == 0) ? 1 : 0;
    }
    if (!debug_enabled && level < LOG_LEVEL_WARN) {
        return;
    }
    
    const char *level_strings[] = { "DEBUG", "INFO", "WARN", "ERROR" };
    time_t now = time(NULL);
    char time_str[20];
    strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", localtime(&now));

    va_list args;
    va_start(args, format);
    fprintf(stderr, "[%s] [PEER_STATS] [%s] ", time_str, level_strings[level]);
    fprintf(stderr, "[%s] [%s] ", time_str, level_strings[level]);
    vfprintf(stderr, format, args);
    fprintf(stderr, "\n");
    va_end(args);

    // Write to debug file if debug mode is active and we have a valid file pointer
    if (g_debug_active_peer && g_debug_fp_peer_ptr && *g_debug_fp_peer_ptr) {
        va_list args2;
        va_start(args2, format);
        fprintf(*g_debug_fp_peer_ptr, "[%s] [PEER_STATS] [%s] ", time_str, level_strings[level]);
        vfprintf(*g_debug_fp_peer_ptr, format, args2);
        fprintf(*g_debug_fp_peer_ptr, "\n");
        fflush(*g_debug_fp_peer_ptr);
        va_end(args2);
    }
}

typedef struct {
    char wlan_name[32];
    int link_id;
    int frequency;
    int channel_number;
} WlanLinkFreq;

// Debuggability control functions for peer_stats
void peer_stats_set_debug_file_ptr(FILE **debug_fp_ptr) {
    g_debug_fp_peer_ptr = debug_fp_ptr;
}

void peer_stats_set_debug_file(const char *debug_file_path) {
    // This function is now a no-op since file management is handled by fault_detection.c
    // Kept for API compatibility
    (void)debug_file_path;
}

void peer_stats_enable_debug(void) {
    g_debug_active_peer = 1;
}

void peer_stats_disable_debug(void) {
    g_debug_active_peer = 0;
    // Note: We don't close the file here since it's managed by fault_detection.c
}

int peer_stats_is_debug_active(void) {
    return g_debug_active_peer;
}

int parse_center_freqs_and_build_map(int *active_freqs, int max_active_freqs, WlanLinkFreq *freq_map, int max_map_entries, int *map_count) {
    FILE *fp = popen("iw dev", "r");
    if (!fp) return 0;

    char line[512];
    char current_wlan[32] = {0};
    int current_link = -1;
    int active_count = 0;
    *map_count = 0;
    int in_link_section = 0;
    int current_channel = 0;
    
    while (fgets(line, sizeof(line), fp)) {
        if (strstr(line, "Interface ") && strstr(line, "wlan")) {
            char *wlan_start = strstr(line, "wlan");
            if (wlan_start) {
                char *wlan_end = strchr(wlan_start, '\n');
                if (!wlan_end) wlan_end = strchr(wlan_start, ' ');
                if (!wlan_end) wlan_end = wlan_start + strlen(wlan_start);
                
                int wlan_len = wlan_end - wlan_start;
                if (wlan_len > 0 && wlan_len < sizeof(current_wlan)) {
                    strlcpy(current_wlan, wlan_start, wlan_len + 1);
                }
            }
            current_link = -1;
            in_link_section = 0;
            current_channel = 0;
        }
        else if (strstr(line, "link ") && strchr(line, ':')) {
            char *link_ptr = strstr(line, "link ");
            if (link_ptr) {
                current_link = atoi(link_ptr + strlen("link "));
                in_link_section = 1;
                current_channel = 0;
            }
        }
        else if (strstr(line, "center1:") && strstr(line, "channel")) {
            char *channel_ptr = strstr(line, "channel");
            if (channel_ptr) {
                channel_ptr += strlen("channel");
                while (*channel_ptr == ' ') channel_ptr++;
                current_channel = atoi(channel_ptr);
                log_message_peer(LOG_LEVEL_DEBUG, "Found channel number: %d for %s link %d", 
                    current_channel, current_wlan, current_link);
            }
            char *center1_ptr = strstr(line, "center1:");
            if (center1_ptr) {
                center1_ptr += strlen("center1:");
                while (*center1_ptr == ' ') center1_ptr++; 
                int frequency = atoi(center1_ptr);
                
                if (frequency > 0) {
                    int found_active = 0;
                    for (int i = 0; i < active_count; i++) {
                        if (active_freqs[i] == frequency) {
                            found_active = 1;
                            break;
                        }
                    }
                    if (!found_active && active_count < max_active_freqs) {
                        active_freqs[active_count++] = frequency;
                    }
                    if (in_link_section && strlen(current_wlan) > 0 && current_link >= 0 && *map_count < max_map_entries) {
                        strlcpy(freq_map[*map_count].wlan_name, current_wlan, sizeof(freq_map[*map_count].wlan_name));
                        freq_map[*map_count].link_id = current_link;
                        freq_map[*map_count].frequency = frequency;
                        freq_map[*map_count].channel_number = current_channel; 
                        (*map_count)++;
                        
                        log_message_peer(LOG_LEVEL_DEBUG, "Mapped %s link %d -> %d MHz (channel %d)", 
                            current_wlan, current_link, frequency, current_channel);
                    }
                }
                in_link_section = 0;
            }
        }
    }
    if(fp){
        pclose(fp);
    }
    return active_count;
}

int get_radio_center_freq_peer(const char *folder_name) {
    char echo_path[MAX_PATH_PEER];
    char read_path[MAX_PATH_PEER];
    FILE *echo_file = NULL;
    FILE *read_file = NULL;
    char stat_buf[CMD_LEN_PEER];
    int freq_val = 0;

    snprintf(echo_path, MAX_PATH_PEER, "%s%s%s", stat_folder_prefix_peer, folder_name, suffix_echo_peer);
    snprintf(read_path, MAX_PATH_PEER, "%s%s%s", stat_folder_prefix_peer, folder_name, suffix_read_peer);

    char echo_cmd[CMD_LEN_PEER];
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
    if(read_file){
        fclose(read_file);
    }
    return freq_val;
}

typedef struct {
    int frequency;
    float channel_utilization;
} RadioChannelUtil;

float get_radio_channel_utilization(const char *folder_name) {
    char echo_path[MAX_PATH_PEER];
    char read_path[MAX_PATH_PEER];
    FILE *echo_file = NULL;
    FILE *read_file = NULL;
    char stat_buf[CMD_LEN_PEER];
    long long int rx_clear_sum = 0;
    long long int usec_cnt_sum = 0;
    long long int current_collection_interval = 0;
    long long int current_rx_clear = 0;
    long long int current_usec_cnt = 0;
    int in_interval_100 = 0;
    int has_rx_clear = 0;
    int has_usec_cnt = 0;
    int intervals_with_100 = 0;
    float channel_util = 0.0;

    snprintf(echo_path, MAX_PATH_PEER, "%s%s%s", stat_folder_prefix_peer, folder_name, suffix_echo_peer);
    snprintf(read_path, MAX_PATH_PEER, "%s%s%s", stat_folder_prefix_peer, folder_name, suffix_read_peer);

    char echo_cmd[CMD_LEN_PEER];
    snprintf(echo_cmd, sizeof(echo_cmd), "echo 19 > %s", echo_path);
    echo_file = popen(echo_cmd, "w");
    if (echo_file == NULL) {
        log_message_peer(LOG_LEVEL_ERROR, "Failed to run echo command: %s", echo_cmd);
        return 0.0;
    }
    pclose(echo_file);

    read_file = fopen(read_path, "r");
    if (read_file == NULL) {
        log_message_peer(LOG_LEVEL_ERROR, "Failed to open read file: %s", read_path);
        return 0.0;
    }

    while(fgets(stat_buf, sizeof(stat_buf), read_file) != NULL) {
        char *ptr;
        
        if((ptr = strstr(stat_buf, "collection_interval ="))) {
            
            current_collection_interval = atoll(ptr + strlen("collection_interval ="));
            
            in_interval_100 = (current_collection_interval == 100);
            has_rx_clear = 0;
            has_usec_cnt = 0;
            current_rx_clear = 0;
            current_usec_cnt = 0;
            
        } else if(in_interval_100 && (ptr = strstr(stat_buf, "rx_clear_usec ="))) {
            long long int rx_clear_val = atoll(ptr + strlen("rx_clear_usec ="));
            current_rx_clear += rx_clear_val;
            
        } else if(in_interval_100 && (ptr = strstr(stat_buf, "usec_cnt ="))) {
            long long int usec_cnt_val = atoll(ptr + strlen("usec_cnt ="));
            current_usec_cnt += usec_cnt_val;
            
            rx_clear_sum += current_rx_clear;
            usec_cnt_sum += current_usec_cnt;
            log_message_peer(LOG_LEVEL_DEBUG, "Added pair: rx_clear=%lld, usec_cnt=%lld (running sums: rx_clear_sum=%lld, usec_cnt_sum=%lld)", 
                current_rx_clear, current_usec_cnt, rx_clear_sum, usec_cnt_sum);
            current_rx_clear = 0;
            current_usec_cnt = 0;
        }
    }
    
    if (usec_cnt_sum > 0) {
        channel_util = ((float)rx_clear_sum / (float)usec_cnt_sum) * 100.0;
        log_message_peer(LOG_LEVEL_DEBUG, "Calculated channel utilization: %.2f%% (rx_clear_sum=%lld, usec_cnt_sum=%lld)", 
            channel_util, rx_clear_sum, usec_cnt_sum);
    } else {
        log_message_peer(LOG_LEVEL_WARN, "No valid data found: usec_cnt_sum=%lld", usec_cnt_sum);
    }
    fclose(read_file);
    return channel_util;
}

int collect_channel_utilization_for_active_radios(WlanLinkFreq *freq_map, int freq_map_size, RadioChannelUtil *radio_utils, int max_radios) {
    DIR *dir = opendir(stat_folder_prefix_peer);
    if (dir == NULL) {
        log_message_peer(LOG_LEVEL_ERROR, "Failed to open directory: %s", stat_folder_prefix_peer);
        return 0;
    }

    struct dirent *entry;
    int util_count = 0;

    int active_freqs[MAX_RADIO_FREQS_PEER];
    int active_count = 0;
    
    for (int i = 0; i < freq_map_size; i++) {
        int found = 0;
        for (int j = 0; j < active_count; j++) {
            if (active_freqs[j] == freq_map[i].frequency) {
                found = 1;
                break;
            }
        }
        if (!found && active_count < MAX_RADIO_FREQS_PEER) {
            active_freqs[active_count++] = freq_map[i].frequency;
        }
    }

    while ((entry = readdir(dir)) != NULL && util_count < max_radios) {
        if ((strstr(entry->d_name, "pci") != NULL) || (strstr(entry->d_name, "ahb") != NULL)) {
            char radio_path[MAX_PATH_PEER];
            snprintf(radio_path, sizeof(radio_path), "%s%s", stat_folder_prefix_peer, entry->d_name);

            DIR *macdir = opendir(radio_path);
            if (!macdir) {
                log_message_peer(LOG_LEVEL_DEBUG, "Could not open radio directory: %s", radio_path);
                continue;
            }

            struct dirent *macentry;
            while ((macentry = readdir(macdir)) != NULL && util_count < max_radios) {
                if (strncmp(macentry->d_name, "mac", 3) == 0) {
                    char folder_name[MAX_PATH_PEER];
                    snprintf(folder_name, sizeof(folder_name), "%s/%s", entry->d_name, macentry->d_name);

                    int freq = get_radio_center_freq_peer(folder_name);
                    
                    int found_active = 0;
                    for (int j = 0; j < active_count; j++) {
                        if (freq == active_freqs[j]) {
                            found_active = 1;
                            break;
                        }
                    }

                    if (found_active) {
                        float channel_util = get_radio_channel_utilization(folder_name);
                        if (channel_util >= 0) {
                            radio_utils[util_count].frequency = freq;
                            radio_utils[util_count].channel_utilization = channel_util;
                            log_message_peer(LOG_LEVEL_DEBUG, "Radio %s: freq=%d MHz, channel_util=%f%%", 
                                folder_name, freq, channel_util);
                            util_count++;
                        }
                    } else {
                        log_message_peer(LOG_LEVEL_DEBUG, "Skipping inactive radio %s (freq %d MHz)", folder_name, freq);
                    }
                }
            }
            if(macdir){
                closedir(macdir);
            }
        }
    }
    if(dir){
        closedir(dir);
    }
    log_message_peer(LOG_LEVEL_DEBUG, "Collected channel utilization for %d radios", util_count);
    return util_count;
}

void echo_to_all_active_radios(WlanLinkFreq *freq_map, int *freq_map_size)
{
    DIR *dir = opendir(stat_folder_prefix_peer);
    if (dir == NULL) {
        perror("opendir failed");
        return;
    }

    struct dirent *entry;
    int count = 0;

    int active_freqs[MAX_RADIO_FREQS_PEER];
    int active_count = parse_center_freqs_and_build_map(active_freqs, MAX_RADIO_FREQS_PEER, freq_map, MAX_PEERS, freq_map_size);


    while ((entry = readdir(dir)) != NULL) {
        if ((strstr(entry->d_name, "pci") != NULL) || (strstr(entry->d_name, "ahb") != NULL)) {
            char radio_path[MAX_PATH_PEER];
            snprintf(radio_path, sizeof(radio_path), "%s%s", stat_folder_prefix_peer, entry->d_name);

            DIR *macdir = opendir(radio_path);
            if (!macdir){
                log_message_peer(LOG_LEVEL_DEBUG, "Folder could not be iterated: %s\n", radio_path);
                continue;
            }

            struct dirent *macentry;
            while ((macentry = readdir(macdir)) != NULL) {
                if (strncmp(macentry->d_name, "mac", 3) == 0) {
                    char folder_name[MAX_PATH_PEER];
                    snprintf(folder_name, sizeof(folder_name), "%s/%s", entry->d_name, macentry->d_name);

                    int freq = get_radio_center_freq_peer(folder_name);
                    int found = 0;
                    for (int j = 0; j < active_count; j++) {
                        if (freq == active_freqs[j]) {
                            found = 1;
                            break;
                        }
                    }
                    if (found) {
                        char echo_path[MAX_PATH_PEER];
                        snprintf(echo_path, sizeof(echo_path), "%s%s/%s%s", stat_folder_prefix_peer, entry->d_name, macentry->d_name, suffix_echo_peer);

                        char echo_cmd[MAX_PATH_PEER + 32];
                        snprintf(echo_cmd, sizeof(echo_cmd), "echo 11 > %s", echo_path);

                        log_message_peer(LOG_LEVEL_DEBUG, "Executing: %s", echo_cmd);
                        FILE *echo_file = popen(echo_cmd, "w");
                        if (echo_file) pclose(echo_file);

                        count++;
                    } else {
                        log_message_peer(LOG_LEVEL_DEBUG, "Skipping %s (freq %d not active)\n", folder_name, freq);
                    }
                }
            }
            if(macdir){
                closedir(macdir);
            }
        }
    }
    if(dir){
        closedir(dir);
    }
}

int get_netdev_folders(char netdevs[MAX_NETDEVS_PEER][MAX_PATH_PEER], int *count)
{
    DIR *dir = opendir(netdev_folder_location);
    if (!dir) return -1;
    struct dirent *entry;
    int idx = 0;
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_type == DT_DIR && strncmp(entry->d_name, "phy", 3) == 0 && idx < MAX_NETDEVS_PEER) {
            char phy_path[MAX_PATH_PEER];
            strlcpy(phy_path, netdev_folder_location, sizeof(phy_path));
            strlcat(phy_path, entry->d_name, sizeof(phy_path));
            DIR *phy_dir = opendir(phy_path);
            if (!phy_dir) continue;
            struct dirent *subentry;
            while ((subentry = readdir(phy_dir)) != NULL) {
                if (subentry->d_type == DT_DIR && strncmp(subentry->d_name, "netdev:", 7) == 0) {
                    strlcpy(netdevs[idx], phy_path, sizeof(netdevs[idx]));
                    strlcat(netdevs[idx], "/", sizeof(netdevs[idx]));
                    strlcat(netdevs[idx], subentry->d_name, sizeof(netdevs[idx]));
                    log_message_peer(LOG_LEVEL_DEBUG, "Found netdev folder: %s", netdevs[idx]);
                    idx++;
                }
            }
            closedir(phy_dir);
        }
    }
    closedir(dir);
    *count = idx;
    return 0;
}

int get_station_macs(const char *netdev_folder, char macs[MAX_MACS_PER_NETDEV][18], int *count)
{
    char stations_path[MAX_PATH_PEER];
    strlcpy(stations_path, netdev_folder, sizeof(stations_path));
    strlcat(stations_path, "/stations/", sizeof(stations_path));
    DIR *dir = opendir(stations_path);
    if (!dir) return -1;
    struct dirent *entry;
    int idx = 0;
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_type == DT_DIR && strlen(entry->d_name) == 17 && idx < MAX_MACS_PER_NETDEV) {
            strlcpy(macs[idx], entry->d_name, 18);
            log_message_peer(LOG_LEVEL_DEBUG, "Found MAC: %s in %s", macs[idx], stations_path);
            idx++;
        }
    }
    closedir(dir);
    *count = idx;
    return 0;
}

int get_link_folders(const char *mac_folder, char link_folders[MAX_LINKS_PEER][MAX_PATH_PEER], int *link_count)
{
    char stations_path[MAX_PATH_PEER];
    snprintf(stations_path, sizeof(stations_path), "%s", mac_folder);

    DIR *dir = opendir(stations_path);
    if (!dir) return -1;

    struct dirent *entry;
    int idx = 0;
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_type == DT_DIR && strncmp(entry->d_name, "link-", 5) == 0 && idx < MAX_LINKS_PEER) {
            snprintf(link_folders[idx], MAX_PATH_PEER, "%s/%s", stations_path, entry->d_name);
            idx++;
        }
    }
    closedir(dir);
    *link_count = idx;
    return 0;
}

void parse_tx_mcs_array(const char *line, PeerStats *stats)
{
    uint32_t mcs_values[TX_MCS_MAX] = {0};
    char *ptr = strstr(line, "tx_mcs =");
    if (!ptr) return;

    for (int i = 0; i < TX_MCS_MAX; i++) {
        char search_str[8];
        snprintf(search_str, sizeof(search_str), "%d:", i);
        char *mcs_ptr = strstr(ptr, search_str);
        if (mcs_ptr) {
            if (i < 10) {
                if (mcs_ptr > ptr && isdigit(*(mcs_ptr - 1))) {
                    continue;
                }
            }
            mcs_values[i] = (uint32_t)strtoul(mcs_ptr + strlen(search_str), NULL, 10);
        }
    }

    for (int i = 0; i < TX_MCS_MAX; i++) {
        stats->tx_mcs[i] = mcs_values[i];
    }
}

void parse_rx_mcs_array(const char *line, PeerStats *stats)
{
    uint32_t mcs_values[RX_MCS_MAX] = {0};
    char *ptr = strstr(line, "rx_mcs =");
    if (!ptr) return;

    for (int i = 0; i < RX_MCS_MAX; i++) {
        char search_str[8];
        snprintf(search_str, sizeof(search_str), "%d:", i);
        char *mcs_ptr = strstr(ptr, search_str);
        if (mcs_ptr) {
            if (i < 10) {
                if (mcs_ptr > ptr && isdigit(*(mcs_ptr - 1))) {
                    continue;
                }
            }
            mcs_values[i] = (uint32_t)strtoul(mcs_ptr + strlen(search_str), NULL, 10);
        }
    }

    for (int i = 0; i < RX_MCS_MAX; i++) {
        stats->rx_mcs[i] = mcs_values[i];
    }
}

void parse_tx_ppdu_bw_array(const char *line, PeerStats *stats)
{
    uint32_t bw_values[TX_PPDU_BW_MAX] = {0};
    char *ptr = strstr(line, "tx_bw =");
    if (!ptr) return;

    for (int i = 0; i < TX_PPDU_BW_MAX; i++) {
        char search_str[8];
        snprintf(search_str, sizeof(search_str), "%d:", i);
        char *bw_ptr = strstr(ptr, search_str);
        if (bw_ptr) {
            if (bw_ptr > ptr && isdigit(*(bw_ptr - 1))) {
                continue;
            }
            bw_values[i] = (uint32_t)strtoul(bw_ptr + strlen(search_str), NULL, 10);
        }
    }

    for (int i = 0; i < TX_PPDU_BW_MAX; i++) {
        stats->tx_ppdu_bw[i] = bw_values[i];
    }
}

void parse_rx_ppdu_bw_array(const char *line, PeerStats *stats)
{
    uint32_t bw_values[RX_PPDU_BW_MAX] = {0};
    char *ptr = strstr(line, "rx_bw =");
    if (!ptr) return;

    for (int i = 0; i < RX_PPDU_BW_MAX; i++) {
        char search_str[8];
        snprintf(search_str, sizeof(search_str), "%d:", i);
        char *bw_ptr = strstr(ptr, search_str);
        if (bw_ptr) {
            if (bw_ptr > ptr && isdigit(*(bw_ptr - 1))) {
                continue;
            }
            bw_values[i] = (uint32_t)strtoul(bw_ptr + strlen(search_str), NULL, 10);
        }
    }

    for (int i = 0; i < RX_PPDU_BW_MAX; i++) {
        stats->rx_ppdu_bw[i] = bw_values[i];
    }
}

void extract_wlan_name(const char *netdev_path, char *wlan_name, size_t wlan_name_size) {
    const char *netdev_prefix = "netdev:";
    const char *netdev_start = strstr(netdev_path, netdev_prefix);
    if (netdev_start) {
        netdev_start += strlen(netdev_prefix);
        snprintf(wlan_name, wlan_name_size, "%s", netdev_start);
    } else {
        wlan_name[0] = '\0';
    }
}


int get_frequency_for_wlan_link(const WlanLinkFreq *freq_map, int map_size, const char *wlan_name, int link_id) {
    for (int i = 0; i < map_size; i++) {
        if (strcmp(freq_map[i].wlan_name, wlan_name) == 0 && freq_map[i].link_id == link_id) {
            return freq_map[i].frequency;
        }
    }
    return 0;
}

int get_channel_for_wlan_link(const WlanLinkFreq *freq_map, int map_size, const char *wlan_name, int link_id) {
    for (int i = 0; i < map_size; i++) {
        if (strcmp(freq_map[i].wlan_name, wlan_name) == 0 && freq_map[i].link_id == link_id) {
            return freq_map[i].channel_number;
        }
    }
    return 0;
}

void update_peer_bandwidth(AllPeerStats *all_stats, const char *station_mac, const char *link_mac, int bandwidth) {
    for (PeerStatsNode *node = all_stats->head; node; node = node->next) {
        if (strcmp(node->stats.mld_mac, station_mac) == 0 && 
            strcmp(node->stats.link_mac, link_mac) == 0) {
            node->stats.association_bandwidth = bandwidth;
            log_message_peer(LOG_LEVEL_DEBUG, "Updated bandwidth for %s/%s: %d MHz", 
                station_mac, link_mac, bandwidth);
            break;
        }
    }
}

void collect_association_bandwidth(AllPeerStats *all_stats, char netdevs[MAX_NETDEVS_PEER][MAX_PATH_PEER], int netdev_count) {
    for (int i = 0; i < netdev_count; i++) {
        char wlan_name[32];
        extract_wlan_name(netdevs[i], wlan_name, sizeof(wlan_name));
        
        if (strlen(wlan_name) == 0) continue;
        
        char cmd[CMD_LEN_PEER];
        snprintf(cmd, sizeof(cmd), "iw dev %s station dump", wlan_name);
        
        FILE *fp = popen(cmd, "r");
        if (!fp) continue;
        
        char line[512];
        char current_station_mac[18] = {0};
        char current_link_mac[18] = {0};
        int bandwidth = 0;
        int in_link_section = 0;
        
        while (fgets(line, sizeof(line), fp)) {
            if (strncmp(line, "Station ", 8) == 0) {
                if (strlen(current_station_mac) > 0 && strlen(current_link_mac) > 0 && bandwidth > 0) {
                    update_peer_bandwidth(all_stats, current_station_mac, current_link_mac, bandwidth);
                }
                
                char *mac_start = strchr(line, ' ');
                if (mac_start) {
                    mac_start++;
                    char *mac_end = strchr(mac_start, ' ');
                    if (mac_end) {
                        int mac_len = mac_end - mac_start;
                        if (mac_len < sizeof(current_station_mac)) {
                            strlcpy(current_station_mac, mac_start, mac_len + 1);
                            strlcpy(current_link_mac, current_station_mac, sizeof(current_link_mac));
                            bandwidth = 0;
                            in_link_section = 0;
                        }
                    }
                }
            }
            else if (strstr(line, "Link ") && strchr(line, ':')) {
                if (strlen(current_station_mac) > 0 && strlen(current_link_mac) > 0 && bandwidth > 0) {
                    update_peer_bandwidth(all_stats, current_station_mac, current_link_mac, bandwidth);
                }
                in_link_section = 1;
                bandwidth = 0;
            }
            else if (in_link_section && strstr(line, "address:")) {
                char *addr_start = strstr(line, "address:");
                if (addr_start) {
                    addr_start += strlen("address:");
                    while (*addr_start == ' ' || *addr_start == '\t') addr_start++;
                    char *addr_end = strchr(addr_start, '\n');
                    if (addr_end) {
                        int addr_len = addr_end - addr_start;
                        if (addr_len < sizeof(current_link_mac)) {
                            strlcpy(current_link_mac, addr_start, addr_len + 1);
                        }
                    }
                }
            }
            else if (strstr(line, "tx bitrate:")) {
                char *mhz_ptr = strstr(line, "MHz");
                if (mhz_ptr) {
                    char *start = mhz_ptr - 1;
                    while (start > line && *start != ' ') {
                        start--;
                    }
                    if (*start == ' ') {
                        start++;
                    }
                    bandwidth = atoi(start);
                    log_message_peer(LOG_LEVEL_DEBUG, "Extracted bandwidth: %d MHz from tx bitrate line: %s", bandwidth, line);
                }
            }
            else if (strstr(line, "rx bitrate:") && bandwidth == 0) {
                char *mhz_ptr = strstr(line, "MHz");
                if (mhz_ptr) {
                    char *start = mhz_ptr - 1;
                    while (start > line && *start != ' ') {
                        start--;
                    }
                    if (*start == ' ') {
                        start++;
                    }
                    bandwidth = atoi(start);
                    log_message_peer(LOG_LEVEL_DEBUG, "Extracted bandwidth: %d MHz from rx bitrate line: %s", bandwidth, line);
                }
            }
        }
        
        if (strlen(current_station_mac) > 0 && bandwidth > 0) {
            update_peer_bandwidth(all_stats, current_station_mac, current_link_mac, bandwidth);
        }
        
        pclose(fp);
    }
}

int parse_stats_from_file(FILE *fp, PeerStats *stats, FILE *raw_fp) {
    char line[512];
    int lines_read = 0;
    uint64_t total_processed_msdu_count = 0;

    while (fgets(line, sizeof(line), fp)) {
        lines_read++;
        if (raw_fp) {
            if (fprintf(raw_fp, "%s", line) < 0) {
                perror("Error writing to raw peer stats file");
            }
        }
        char *ptr;
        if ((ptr = strstr(line, "last_rssi ="))) {
            stats->rx_rssi = (int32_t)atoi(ptr + strlen("last_rssi ="));
            if (stats->rx_rssi >= RSSI_EXCELLENT_THRESHOLD) {
                stats->rssi_status = RSSI_STATUS_EXCELLENT;
            } else if (stats->rx_rssi >= RSSI_GOOD_THRESHOLD) {
                stats->rssi_status = RSSI_STATUS_GOOD;
            } else if (stats->rx_rssi >= RSSI_FAIR_THRESHOLD) {
                stats->rssi_status = RSSI_STATUS_FAIR;
            } else {
                stats->rssi_status = RSSI_STATUS_POOR;
            }
        } else if ((ptr = strstr(line, "ppdu_cnt ="))) {
            stats->rx_ppdu_cnt = (uint64_t)atoll(ptr + strlen("ppdu_cnt ="));
        } else if ((ptr = strstr(line, "tx_removed_mpdu_cnt ="))) {
            stats->tx_removed_mpdu_cnt = (uint64_t)atoll(ptr + strlen("tx_removed_mpdu_cnt ="));
        } else if ((ptr = strstr(line, "mpdu_cnt ="))) {
            stats->rx_mpdu_success_cnt = (uint64_t)atoll(ptr + strlen("mpdu_cnt ="));
        } else if ((ptr = strstr(line, "tx_mcs ="))) {
            parse_tx_mcs_array(line, stats);
        } else if ((ptr = strstr(line, "rx_mcs ="))) {
            parse_rx_mcs_array(line, stats);
        } else if ((ptr = strstr(line, "transmitted_ppdu_bytes ="))) {
            stats->dl_speed = (uint64_t)atoll(ptr + strlen("transmitted_ppdu_bytes ="));
        } else if ((ptr = strstr(line, "tx_bw =")) && ptr == line) {
            parse_tx_ppdu_bw_array(line, stats);
        } else if ((ptr = strstr(line, "rx_bw =")) && ptr == line) {
            parse_rx_ppdu_bw_array(line, stats);
        } else if ((ptr = strstr(line, "mac_addr = "))) {
            ptr += strlen("mac_addr = ");
            strlcpy(stats->link_mac, ptr, sizeof(stats->link_mac));
        } else if ((ptr = strstr(line, "tx_ppdu_cnt ="))) {
            stats->tx_ppdu_cnt = (uint64_t)atoll(ptr + strlen("tx_ppdu_cnt ="));
        } else if ((ptr = strstr(line, "tx_mpdu_try_cnt ="))) {
            stats->tx_mpdu_try_cnt = (uint64_t)atoll(ptr + strlen("tx_mpdu_try_cnt ="));
        } else if ((ptr = strstr(line, "tx_mpdu_success_cnt ="))) {
            stats->tx_mpdu_success_cnt = (uint64_t)atoll(ptr + strlen("tx_mpdu_success_cnt ="));
        } else if ((ptr = strstr(line, "rx_mpdu_try_cnt ="))) {
            stats->rx_mpdu_try_cnt = (uint64_t)atoll(ptr + strlen("rx_mpdu_try_cnt ="));
        } else if ((ptr = strstr(line, "rx_ppdu_bytes ="))) {
            stats->ul_speed = (uint64_t)atoll(ptr + strlen("rx_ppdu_bytes ="));
        } else if ((ptr = strstr(line, "total_processed_msdu_count ="))) {
            uint64_t msdu_count = (uint64_t)atoll(ptr + strlen("total_processed_msdu_count ="));
            total_processed_msdu_count += msdu_count;
        }
    }
    
    if (stats->tx_mpdu_try_cnt > 0) {
        stats->tx_per = (1.0 - (float)stats->tx_mpdu_success_cnt / (float)stats->tx_mpdu_try_cnt) * 100.0;
    } else {
        stats->tx_per = 0.0;
    }
    
    if (stats->rx_mpdu_try_cnt > 0) {
        stats->rx_per = (1.0 - (float)stats->rx_mpdu_success_cnt / (float)stats->rx_mpdu_try_cnt) * 100.0;
    } else {
        stats->rx_per = 0.0;
    }
    
    stats->tx_msdu_count = total_processed_msdu_count;
    
    stats->peer_status = PEER_STATUS_UNKNOWN;
    return lines_read;
}

int parse_peer_stats_file(const char *filepath, PeerStats *stats, FILE *raw_fp, int peer_index)
{
    FILE *fp = fopen(filepath, "r");
    if (!fp) {
        log_message_peer(LOG_LEVEL_DEBUG, "Could not open %s", filepath);
        return -1;
    }
    
    if (raw_fp) {
        fprintf(raw_fp, "\n# Peer %d - MAC: %s\n", peer_index, stats->mld_mac);
    }
    int lines_read = parse_stats_from_file(fp, stats, raw_fp);
    fclose(fp);
    
    // Retry once if no lines were read
    if (lines_read == 0) {
        log_message_peer(LOG_LEVEL_DEBUG, "No lines read from %s, retrying once", filepath);
        fp = fopen(filepath, "r");
        if (!fp) {
            log_message_peer(LOG_LEVEL_DEBUG, "Could not open %s on retry", filepath);
            return -1;
        }
        
        lines_read = parse_stats_from_file(fp, stats, raw_fp);
        fclose(fp);
    }
    
    log_message_peer(LOG_LEVEL_DEBUG, "Read %d lines from %s", lines_read, filepath);

    return 0;
}

int get_all_peer_stats(AllPeerStats *all_stats, const char *filepath)
{
    char netdevs[MAX_NETDEVS_PEER][MAX_PATH_PEER];
    int netdev_count = 0;
    int ret = 0;
    FILE *raw_fp = NULL;

    raw_fp = fopen(filepath, "w");
    if (!raw_fp) {
        log_message_peer(LOG_LEVEL_ERROR, "Failed to open raw output file: %s", filepath);
        ret = 0;
        goto end;
    }

    if (get_netdev_folders(netdevs, &netdev_count) != 0) {
        log_message_peer(LOG_LEVEL_ERROR, "Failed to get netdev folders");
        all_stats->count = 0;
        all_stats->head = NULL;
        all_stats->tail = NULL;
        ret = 0;
        goto end;
    }

    WlanLinkFreq *freq_map = (WlanLinkFreq *)calloc(MAX_PEERS, sizeof(WlanLinkFreq));;
    int freq_map_size = 0;
    if (!freq_map) {
        log_message_peer(LOG_LEVEL_ERROR, "Failed to allocate memory for frequency map");
        all_stats->count = 0;
        all_stats->head = NULL;
        all_stats->tail = NULL;
        ret = 0;
        goto end;
    }
    
    echo_to_all_active_radios(freq_map, &freq_map_size);
    log_message_peer(LOG_LEVEL_DEBUG, "Built frequency map with %d entries", freq_map_size);

    // Wait for peerstats to be populated
    usleep(100000);

    all_stats->count = 0;
    all_stats->head = NULL;
    all_stats->tail = NULL;

    for (int i = 0; i < netdev_count; ++i) {
        char macs[MAX_MACS_PER_NETDEV][18];
        int mac_count = 0;
        if (get_station_macs(netdevs[i], macs, &mac_count) != 0) {
            continue;
        }
        for (int m = 0; m < mac_count; ++m) {
            char mac_folder[MAX_PATH_PEER];
            snprintf(mac_folder, sizeof(mac_folder), "%s/stations/%s", netdevs[i], macs[m]);

            char link_folders[MAX_LINKS_PEER][MAX_PATH_PEER];
            int link_count = 0;
            if (get_link_folders(mac_folder, link_folders, &link_count) != 0) {
                log_message_peer(LOG_LEVEL_DEBUG, "No Link folders found in %s", mac_folder);
                continue;
            }

            for (int l = 0; l < link_count; ++l) {
                if (all_stats->count >= MAX_PEERS) break;
                char stats_path[MAX_PATH_PEER];
                snprintf(stats_path, sizeof(stats_path), "%s/htt_peer_stats", link_folders[l]);

                PeerStatsNode *node = (PeerStatsNode *)malloc(sizeof(PeerStatsNode));
                if (!node) {
                    log_message_peer(LOG_LEVEL_ERROR, "Failed to allocate PeerStatsNode");
                    continue;
                }
                memset(&node->stats, 0, sizeof(PeerStats));
                node->next = NULL;
                strlcpy(node->stats.mld_mac, macs[m], 18);


                char *link_folder_name = strrchr(link_folders[l], '/');
                int link_id = 0;
                if (link_folder_name && strncmp(link_folder_name + 1, "link-", 5) == 0) {
                    link_id = atoi(link_folder_name + 6);
                }

                char wlan_name[32];
                extract_wlan_name(netdevs[i], wlan_name, sizeof(wlan_name));
                node->stats.frequency_band = get_frequency_for_wlan_link(freq_map, freq_map_size, wlan_name, link_id);
                node->stats.associated_channel_number = get_channel_for_wlan_link(freq_map, freq_map_size, wlan_name, link_id);

                if (parse_peer_stats_file(stats_path, &node->stats, raw_fp, all_stats->count + 1) < 0) {
                    free(node);
                    log_message_peer(LOG_LEVEL_DEBUG, "Error reading peer stats file");
                    continue;
                }

                if (!all_stats->head) {
                    all_stats->head = node;
                    all_stats->tail = node;
                } else {
                    all_stats->tail->next = node;
                    all_stats->tail = node;
                }
                all_stats->count++;

                log_message_peer(LOG_LEVEL_DEBUG, "Collected stats for MAC %s (link folder %s): RSSI=%d RX_PPDU_CNT=%d FREQ=%d ...",
                    node->stats.mld_mac, link_folders[l],
                    node->stats.rx_rssi,
                    node->stats.rx_ppdu_cnt,
                    node->stats.frequency_band
                );
            }
        }
    }
    log_message_peer(LOG_LEVEL_DEBUG, "Final peer count: %d", all_stats->count);

    collect_association_bandwidth(all_stats, netdevs, netdev_count);

    RadioChannelUtil radio_utils[MAX_RADIOS_PEER];
    int radio_util_count = collect_channel_utilization_for_active_radios(freq_map, freq_map_size, radio_utils, MAX_RADIOS_PEER);
    log_message_peer(LOG_LEVEL_DEBUG, "Collected channel utilization for %d radios", radio_util_count);

    for (PeerStatsNode *node = all_stats->head; node; node = node->next) {
        for (int r = 0; r < radio_util_count; r++) {
            if (radio_utils[r].frequency == node->stats.frequency_band) {
                node->stats.channel_utilization = radio_utils[r].channel_utilization;
                log_message_peer(LOG_LEVEL_DEBUG, "Set channel utilization %.2f%% for peer %s on freq %d MHz", 
                    node->stats.channel_utilization, node->stats.mld_mac, node->stats.frequency_band);
                break;
            }
        }
    }
    ret = all_stats->count;
end:
    if (freq_map) {
        free(freq_map);
    }
    if (raw_fp) {
        fclose(raw_fp);
        log_message_peer(LOG_LEVEL_DEBUG, "Raw peer stats saved to %s", filepath);
    }
    return ret;
}


void print_peer_stats(const AllPeerStats *all_stats)
{
    if (!all_stats) {
        log_message_peer(LOG_LEVEL_ERROR, " all_stats is NULL\n");
        goto end;
    }

    int n = all_stats->count;
    if (n < 0) {
        log_message_peer(LOG_LEVEL_WARN, "negative count=%d\n", n);
        goto end;
    }

    log_message_peer(LOG_LEVEL_DEBUG, "---- Peer stats BEGIN (count=%d) ----\n", n);

    int i = 0;
    for (PeerStatsNode *node = all_stats->head; node; node = node->next, ++i) {
        const PeerStats *p = &node->stats;

        // Check if peer is not active (rssi is 0 and other stats are also 0)
        int is_inactive = (p->rx_rssi == 0 && 
                          p->tx_ppdu_cnt == 0 && 
                          p->rx_ppdu_cnt == 0 && 
                          p->tx_mpdu_try_cnt == 0 && 
                          p->rx_mpdu_try_cnt == 0 && 
                          p->dl_speed == 0 && 
                          p->ul_speed == 0);
        
        char rssi_str[16];
        if (is_inactive) {
            strlcpy(rssi_str, "NA", sizeof(rssi_str));
        } else {
            snprintf(rssi_str, sizeof(rssi_str), "%d", p->rx_rssi);
        }
        
        log_message_peer(
            LOG_LEVEL_DEBUG,
            "[%4d] MLD MAC=%s | LINK MAC=%s | FREQ=%d | CHANNEL=%d | RX_RSSI=%s | RSSI_STATUS=%s | TX_PPDU_CNT=%llu | RX_PPDU_CNT=%llu\n",
            i, p->mld_mac,
            p->link_mac,
            p->frequency_band,
            p->associated_channel_number,
            rssi_str,
            is_inactive ? "Unknown" : RSSI_STATUS_STRING(p->rssi_status),
            p->tx_ppdu_cnt,
            p->rx_ppdu_cnt
        );

        log_message_peer(
            LOG_LEVEL_DEBUG,
            "      TX_MPDU_TRY=%llu | TX_REMOVED_MPDU=%llu | TX_MPDU_SUCCESS=%llu | TX_PER=%.2f%% | RX_MPDU_TRY=%llu | RX_MPDU_SUCCESS=%llu | RX_PER=%.2f%%\n",
            p->tx_mpdu_try_cnt,
            p->tx_removed_mpdu_cnt,
            p->tx_mpdu_success_cnt,
            p->tx_per,
            p->rx_mpdu_try_cnt,
            p->rx_mpdu_success_cnt,
            p->rx_per
        );

        log_message_peer(
            LOG_LEVEL_DEBUG,
            "      DL_BYTES=%llu | UL_BYTES=%llu | TX_MSDU_COUNT=%llu | CH_UTIL=%.2f | ASSOC_BW=%d MHz | CLIENT EXPERIENCE=%s\n",
            p->dl_speed,
            p->ul_speed,
            p->tx_msdu_count,
            p->channel_utilization,
            p->association_bandwidth,
            PEER_STATUS_STRING(p->peer_status)
        );

        char line[1024];
        int off = 0;
        off += snprintf(line + off, sizeof(line) - off, "    TX_MCS (index 0 to 15): ");
        for (int m = 0; m < TX_MCS_MAX && off < (int)sizeof(line); ++m) {
            off += snprintf(line + off, sizeof(line) - off, "[%d]=%d ", m, p->tx_mcs[m]);
        }
        off += snprintf(line + off, sizeof(line) - off, "\n");
        log_message_peer(LOG_LEVEL_DEBUG, "%s", line);

        off = 0;
        off += snprintf(line + off, sizeof(line) - off, "    RX_MCS (index 0 to 15): ");
        for (int m = 0; m < RX_MCS_MAX && off < (int)sizeof(line); ++m) {
            off += snprintf(line + off, sizeof(line) - off, "[%d]=%d ", m, p->rx_mcs[m]);
        }
        off += snprintf(line + off, sizeof(line) - off, "\n");
        log_message_peer(LOG_LEVEL_DEBUG, "%s", line);

        off = 0;
        off += snprintf(line + off, sizeof(line) - off, "    TX_PPDU_BW (index 20,40,80,160,320): ");
        for (int b = 0; b < TX_PPDU_BW_MAX && off < (int)sizeof(line); ++b) {
            off += snprintf(line + off, sizeof(line) - off, "[%d]=%d ", b, p->tx_ppdu_bw[b]);
        }
        off += snprintf(line + off, sizeof(line) - off, "\n");
        log_message_peer(LOG_LEVEL_DEBUG, "%s", line);

        off = 0;
        off += snprintf(line + off, sizeof(line) - off, "    RX_PPDU_BW (index 20,40,80,160,320): ");
        for (int b = 0; b < RX_PPDU_BW_MAX && off < (int)sizeof(line); ++b) {
            off += snprintf(line + off, sizeof(line) - off, "[%d]=%d ", b, p->rx_ppdu_bw[b]);
        }
        off += snprintf(line + off, sizeof(line) - off, "\n");
        log_message_peer(LOG_LEVEL_DEBUG, "%s", line);
    }

    log_message_peer(LOG_LEVEL_DEBUG, "---- Peer stats END ----\n");
end:
    return;
}

int write_peer_stats_to_file(const AllPeerStats *all_stats, const char *filepath)
{
    int ret = 0;
    if (!all_stats || !filepath) {
        ret = -1;
        goto end;
    }
    FILE *fp = fopen(filepath, "w");
    if (!fp) {
        log_message_peer(LOG_LEVEL_ERROR, "Failed to open file for writing: %s", filepath);
        ret = -1;
        goto end;
    }

    // Write header
    if (fprintf(fp, "# Peer Stats (count=%d)\n", all_stats->count) < 0) {
        ret = -1;
        goto close_file;
    }
    
    if (fprintf(fp, "%-3s %-17s %-17s %-12s %-5s %-7s %-12s %-7s %-12s %-12s %-16s %-20s %-20s %-8s %-16s %-20s %-8s %-10s %-10s %-10s %-10s %-14s %-60s %-60s %-40s %-40s\n",
            "ID", "MLD MAC", "LINK MAC", "CLIENT EXP", "BAND", "RSSI", "RSSI_STATUS", "CHANNEL", "TX_PPDU", "RX_PPDU", 
            "TX_MPDU_TRY", "TX_MPDU_REMOVED", "TX_MPDU_SUCCESS", "TX_PER", "RX_MPDU_TRY", "RX_MPDU_SUCCESS", "RX_PER",
            "DL_BYTES", "UL_BYTES", "CH_UTIL", "BW", "TX_MSDU_COUNT", "TX_MCS (0-15)", "RX_MCS (0-15)", "TX_PPDU_BW (20,40,80,160,320)", "RX_PPDU_BW (20,40,80,160,320)") < 0) {
        ret = -1;
        goto close_file;
    }

    if (fprintf(fp, "%-3s %-17s %-17s %-12s %-5s %-7s %-12s %-7s %-12s %-12s %-16s %-20s %-20s %-8s %-16s %-20s %-8s %-10s %-10s %-10s %-10s %-14s %-60s %-60s %-40s %-40s\n",
        "---", "-----------------", "-----------------", "------------", "-----", "-------", "------------", "-------", "------------", "------------", 
        "----------------", "--------------------", "--------------------", "--------", "----------------", "--------------------", "--------",
        "----------", "----------", "----------", "----------", "--------------", "------------------------------------------------------------", "------------------------------------------------------------", "----------------------------------------", "----------------------------------------") < 0) {
        ret = -1;
        goto close_file;
    }

    // Table data
    int i = 0;
    for (PeerStatsNode *node = all_stats->head; node; node = node->next, ++i) {
        const PeerStats *p = &node->stats;
        
        char tx_mcs_str[MCS_STR_BUF_SIZE] = {0};
        char rx_mcs_str[MCS_STR_BUF_SIZE] = {0};
        char tx_ppdu_bw_str[BW_STR_BUF_SIZE] = {0};
        char rx_ppdu_bw_str[BW_STR_BUF_SIZE] = {0};
        
        int offset = 0;
        int n = 0;

        offset = 0;
        for (int j = 0; j < TX_MCS_MAX; ++j) {
            n = snprintf(tx_mcs_str + offset, sizeof(tx_mcs_str) - offset, 
                         "%s%d", (j ? "," : ""), p->tx_mcs[j]);
            // Check for truncation or error
            if (n < 0 || n >= (int)(sizeof(tx_mcs_str) - offset)) break;
            offset += n;
        }
        tx_mcs_str[sizeof(tx_mcs_str) - 1] = '\0';
        
        offset = 0;
        for (int j = 0; j < RX_MCS_MAX; ++j) {
            n = snprintf(rx_mcs_str + offset, sizeof(rx_mcs_str) - offset, 
                         "%s%d", (j ? "," : ""), p->rx_mcs[j]);
            if (n < 0 || n >= (int)(sizeof(rx_mcs_str) - offset)) break;
            offset += n;
        }
        rx_mcs_str[sizeof(rx_mcs_str) - 1] = '\0';
        
        offset = 0;
        for (int j = 0; j < TX_PPDU_BW_MAX; ++j) {
            n = snprintf(tx_ppdu_bw_str + offset, sizeof(tx_ppdu_bw_str) - offset, 
                         "%s%d", (j ? "," : ""), p->tx_ppdu_bw[j]);
            if (n < 0 || n >= (int)(sizeof(tx_ppdu_bw_str) - offset)) break;
            offset += n;
        }
        tx_ppdu_bw_str[sizeof(tx_ppdu_bw_str) - 1] = '\0';
        
        offset = 0;
        for (int j = 0; j < RX_PPDU_BW_MAX; ++j) {
            n = snprintf(rx_ppdu_bw_str + offset, sizeof(rx_ppdu_bw_str) - offset, 
                         "%s%d", (j ? "," : ""), p->rx_ppdu_bw[j]);
            if (n < 0 || n >= (int)(sizeof(rx_ppdu_bw_str) - offset)) break;
            offset += n;
        }
        rx_ppdu_bw_str[sizeof(rx_ppdu_bw_str) - 1] = '\0';
        
        // Check if peer is not active (rssi is 0 and other stats are also 0)
        int is_inactive = (p->rx_rssi == 0 && 
                          p->tx_ppdu_cnt == 0 && 
                          p->rx_ppdu_cnt == 0 && 
                          p->tx_mpdu_try_cnt == 0 && 
                          p->rx_mpdu_try_cnt == 0 && 
                          p->dl_speed == 0 && 
                          p->ul_speed == 0);
        
        char rssi_str[16];
        if (is_inactive) {
            strlcpy(rssi_str, "NA", sizeof(rssi_str));
        } else {
            snprintf(rssi_str, sizeof(rssi_str), "%d", p->rx_rssi);
        }
        
        // Write one line per peer
        if (fprintf(fp, "%-3d %-17s %-17s %-12s %-5d %-7s %-12s %-7d %-12llu %-12llu %-16llu %-20llu %-20llu %-8.2f %-16llu %-20llu %-8.2f %-10llu %-10llu %-10.2f %-10d %-14llu %-60s %-60s %-40s %-40s\n",
            i, p->mld_mac, p->link_mac, PEER_STATUS_STRING(p->peer_status), 
            p->frequency_band, 
            rssi_str, 
            is_inactive ? "Unknown" : RSSI_STATUS_STRING(p->rssi_status), 
            p->associated_channel_number, 
            p->tx_ppdu_cnt, p->rx_ppdu_cnt,
            p->tx_mpdu_try_cnt, p->tx_removed_mpdu_cnt, p->tx_mpdu_success_cnt, p->tx_per,
            p->rx_mpdu_try_cnt, p->rx_mpdu_success_cnt, p->rx_per,
            p->dl_speed, p->ul_speed, p->channel_utilization, p->association_bandwidth, p->tx_msdu_count,
            tx_mcs_str, rx_mcs_str, tx_ppdu_bw_str, rx_ppdu_bw_str) < 0) {
            ret = -1;
            goto close_file;
        }
    }
    fflush(fp);

close_file:
    fclose(fp);
end:
    return ret;
}

void classify_peers(AllPeerStats *all_stats)
{
    if (!all_stats || !all_stats->head) {
        log_message_peer(LOG_LEVEL_WARN, "No peers to classify");
        goto end;
    }

    log_message_peer(LOG_LEVEL_DEBUG, "Classifying %d peers", all_stats->count);

    for (PeerStatsNode *node = all_stats->head; node; node = node->next) {
        PeerStats *peer = &node->stats;
        peer->peer_status = PEER_STATUS_UNKNOWN;
        
        float max_per = peer->tx_per > peer->rx_per ? peer->tx_per : peer->rx_per;
        
        if (max_per < PER_EXCELLENT_THRESHOLD) {
            peer->peer_status = PEER_STATUS_EXCELLENT;
        } else if (max_per < PER_GOOD_THRESHOLD) {
            peer->peer_status = PEER_STATUS_GOOD;
        } else if (max_per < PER_FAIR_THRESHOLD) {
            peer->peer_status = PEER_STATUS_FAIR;
        } else {
            peer->peer_status = PEER_STATUS_POOR;
        }
        
        log_message_peer(LOG_LEVEL_DEBUG, 
            "Peer %s: TX_PER=%.2f%%, RX_PER=%.2f%%, Client Experience=%s", 
            peer->mld_mac, peer->tx_per, peer->rx_per,
            PEER_STATUS_STRING(peer->peer_status));
    }
    
    log_message_peer(LOG_LEVEL_INFO, "Peer classification completed");
end:
    return;
}

void free_all_peer_stats(AllPeerStats *all_stats)
{
    PeerStatsNode *node = all_stats->head;
    while (node) {
        PeerStatsNode *next = node->next;
        free(node);
        node = next;
    }
    all_stats->head = NULL;
    all_stats->tail = NULL;
    all_stats->count = 0;
}
