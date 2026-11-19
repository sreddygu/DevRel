/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#include "fault_detection.h"
#include "syslog_processing.h"
#include "debugging.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <regex.h>

// Reason code definitions
ReasonCode reason_definitions[] = {
    {0, "Reserved"}, {1, "Unspecified reason"}, {2, "Previous authentication no longer valid"},
    {3, "Station is leaving (or has left) IBSS or ESS"}, {4, "Disassociated due to inactivity"},
    {5, "AP unable to handle all currently associated stations"}, {6, "Class 2 frame from nonauthenticated station"},
    {7, "Class 3 frame from nonassociated station"}, {8, "Sending station is leaving (or has left) BSS"},
    {9, "Station not authenticated with responding station"}, {10, "Unacceptable Power Capability element"},
    {11, "Unacceptable Supported Channels element"}, {13, "Invalid information element"},
    {14, "Message integrity code (MIC) failure"}, {15, "4-Way Handshake timeout"},
    {16, "Group Key Handshake timeout"}, {17, "Mismatch in 4-Way Handshake and AssocReq"},
    {18, "Invalid group cipher"}, {19, "Invalid pairwise cipher"}, {20, "Invalid AKMP"},
    {21, "Unsupported RSN version"}, {22, "Invalid RSN capabilities"}, {23, "IEEE 802.1X authentication failed"},
    {24, "Cipher suite rejected due to security policy"}, {32, "QoS-related unspecified reason"},
    {33, "QAP lacks bandwidth"}, {34, "Excessive unacknowledged frames"}, {35, "QSTA transmitting outside TXOPs"},
    {36, "Peer QSTA requested disconnect"}, {37, "Peer QSTA does not want to use mechanism"},
    {38, "Peer QSTA received frames needing setup"}, {39, "Peer QSTA timeout"},
    {40, "Peer QSTA unsupported cipher suite"}, {98, "Cisco defined"},
    {99, "Cisco defined - invalid client reason code"}
};

const int reason_definitions_count = sizeof(reason_definitions) / sizeof(reason_definitions[0]);

const char* lookup_reason(int code) {
    int num_reasons = sizeof(reason_definitions) / sizeof(reason_definitions[0]);
    for (int i = 0; i < num_reasons; i++) {
        if (reason_definitions[i].code == code) {
            return reason_definitions[i].description;
        }
    }
    if ((code >= 25 && code <= 31) || (code >= 46 && code <= 65535)) {
        return "Reserved";
    }
    return "Unknown reason code";
}

int regex_match(const char *pattern, const char *text) {
    regex_t regex;
    int ret = regcomp(&regex, pattern, REG_EXTENDED | REG_ICASE);
    if (ret) return 0;
    ret = regexec(&regex, text, 0, NULL, 0);
    regfree(&regex);
    return ret == 0;
}

void print_event(const char *notif_path,
                                const char *mac,
                                const char *link_addr,
                                const char *event,
                                const char *details,
                                const char *log_match,
                                const char *line)
{
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"---- Event ----\n");
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"MAC Address: %s\n", mac);
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Link Address: %s\n", link_addr);
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Event: %s\n", event);
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Details: %s\n", details);
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Log Match: %s\n", log_match);
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"\n");
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Line: %s\n", line);
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"\n");
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"----------------\n");

    // append to file
    char tmp[768];
    (void)snprintf(tmp, sizeof(tmp),
                   "\n\n---- Event ----\n"
                   "MAC Address: %s\n"
                   "Link Address: %s\n"
                   "Event: %s\n"
                   "Details: %s\n"
                   "Log Match: %s\n"
                   "\n"
                   "Line: %s\n"
                   "\n"
                   "----------------\n",
                   mac, link_addr, event, details, log_match, line);

    FILE *f = fopen(notif_path, "a");
    if (f) {
        fputs(tmp, f);
        fclose(f);
    } else {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,
                    "Failed to open anomaly file for append: %s\n", notif_path);
    }
}

// Helper function to add a unique MAC to an array
int add_unique_mac(char macs[][SYS_MAC_LEN], int *mac_count, const char *mac, int max_macs) {
    if (*mac_count >= max_macs) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Cannot add MAC %s, array is full.\n", mac);
        return 0; // Array is full
    }

    for (int i = 0; i < *mac_count; i++) {
        if (strncmp(macs[i], mac, SYS_MAC_LEN) == 0) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "MAC %s is already in the array (duplicate).\n", mac);
            return 0; // Duplicate found
        }
    }

    strlcpy(macs[*mac_count], mac, SYS_MAC_LEN);
    (*mac_count)++;
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Added MAC %s to array, new count: %d\n", mac, *mac_count);
    return 1; // MAC added
}

// Helper function to extract MAC address from authentication line
static int extract_mac_from_authentication_line(const char *line, char *mac_out, size_t mac_out_size) {
    // Look for "authentication: STA=" pattern
    const char *auth_marker = "authentication: STA=";
    const char *pos = strstr(line, auth_marker);
    
    if (pos == NULL) {
        return 0;
    }
    
    // Move past the marker to the MAC address
    pos += strlen(auth_marker);
    
    // Extract MAC address using regex
    regex_t rx_mac;
    const char *pat_mac = "([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})";
    if (regcomp(&rx_mac, pat_mac, REG_EXTENDED | REG_ICASE) != 0) {
        return 0;
    }
    
    regmatch_t m[2];
    if (regexec(&rx_mac, pos, 2, m, 0) == 0) {
        int start = (int)m[1].rm_so;
        int end = (int)m[1].rm_eo;
        if (start >= 0 && end > start && (end - start) < (int)mac_out_size) {
            char saved = pos[end];
            ((char*)pos)[end] = '\0';
            strlcpy(mac_out, pos + start, mac_out_size);
            ((char*)pos)[end] = saved;
            regfree(&rx_mac);
            return 1;
        }
    }
    regfree(&rx_mac);
    return 0;
}

static int parse_mac_for_sae_confirm_mismatch(char **all_lines, int line_idx, char *mac_out, size_t mac_out_size) {
    for (int back_idx = line_idx; back_idx >= 0; back_idx--) {
        if (extract_mac_from_authentication_line(all_lines[back_idx], mac_out, mac_out_size)) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, 
                       "Found MAC %s from authentication line while searching backwards from line %d (pattern: SAE: Confirm mismatch)\n", 
                       mac_out, line_idx);
            return 1;
        }
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG, 
               "No authentication line found when searching backwards from line %d (pattern: SAE: Confirm mismatch)\n", 
               line_idx);
    return 0;
}

int process_syslog(char *sys_path,  const char *notif_path, int anomaly_type) {
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "--- Starting syslog processing for anomaly_type: %d ---\n", anomaly_type);
    FILE *syslog;
    char buffer[SYS_MAX_LEN];
    char disassoc_macs[MAX_MACS][SYS_MAC_LEN];
    char fail_connect_macs[MAX_MACS][SYS_MAC_LEN];
    int disassoc_mac_count = 0;
    int fail_connect_mac_count = 0;

    note_value[0]  = '\0';

    syslog = fopen(sys_path, "r");
    if (syslog == NULL) {
        return 0;
    }

    // Pattern 1-3: "sta_remove -> DEL_STATION ath0/mld0/wlan0 00:03:7f:58:42:78"
    const char *pat_sta_remove = "sta_remove[[:space:]]*->[[:space:]]*DEL_STATION[[:space:]]+(ath[0-9]+|mld[0-9]+|wlan[0-9]+)[[:space:]]+([0-9a-f:]{17})";
    
    // Pattern 4: "daemon.info hostapd: mld0: STA c8:8a:9a:d3:99:9c IEEE 802.11: disassociated"
    const char *pat_disassoc = "daemon\\.info[[:space:]]+hostapd:[[:space:]].*STA[[:space:]]+([0-9a-f:]{17})[[:space:]]+IEEE[[:space:]]+802\\.11:[[:space:]]+disassociated";
    
    // Pattern 5: "Delete station c8:8a:9a:d3:99:9c"
    const char *pat_delete = "Delete[[:space:]]+station[[:space:]]+([0-9a-f:]{17})";

    regex_t rx_sta_remove, rx_disassoc, rx_delete;
    int compiled_sta_remove = 0, compiled_disassoc = 0, compiled_delete = 0;

    if (regcomp(&rx_sta_remove, pat_sta_remove, REG_EXTENDED | REG_ICASE) == 0) {
        compiled_sta_remove = 1;
    }
    if (regcomp(&rx_disassoc, pat_disassoc, REG_EXTENDED | REG_ICASE) == 0) {
        compiled_disassoc = 1;
    }
    if (regcomp(&rx_delete, pat_delete, REG_EXTENDED | REG_ICASE) == 0) {
        compiled_delete = 1;
    }

    if (!compiled_sta_remove && !compiled_disassoc && !compiled_delete) {
        fclose(syslog);
        return 0;
    }

    while (fgets(buffer, sizeof(buffer), syslog) != NULL) {
        char mac[SYS_MAC_LEN] = {0};
        int found = 0;

        // Try pattern 1-3: sta_remove -> DEL_STATION
        if (compiled_sta_remove && !found) {
            regmatch_t m[3];
            if (regexec(&rx_sta_remove, buffer, 3, m, 0) == 0) {
                int start = (int)m[2].rm_so;
                int end   = (int)m[2].rm_eo;
                if (start >= 0 && end > start && (end - start) < SYS_MAC_LEN) {
                    char saved = buffer[end];
                    buffer[end] = '\0';
                    strlcpy(mac, buffer + start, sizeof(mac));
                    buffer[end] = saved;
                    found = 1;
                }
            }
        }

        // Try pattern 4: daemon.info hostapd disassociated
        if (compiled_disassoc && !found) {
            regmatch_t m[2];
            if (regexec(&rx_disassoc, buffer, 2, m, 0) == 0) {
                int start = (int)m[1].rm_so;
                int end   = (int)m[1].rm_eo;
                if (start >= 0 && end > start && (end - start) < SYS_MAC_LEN) {
                    char saved = buffer[end];
                    buffer[end] = '\0';
                    strlcpy(mac, buffer + start, sizeof(mac));
                    buffer[end] = saved;
                    found = 1;
                }
            }
        }

        // Try pattern 5: Delete station
        if (compiled_delete && !found) {
            regmatch_t m[2];
            if (regexec(&rx_delete, buffer, 2, m, 0) == 0) {
                int start = (int)m[1].rm_so;
                int end   = (int)m[1].rm_eo;
                if (start >= 0 && end > start && (end - start) < SYS_MAC_LEN) {
                    char saved = buffer[end];
                    buffer[end] = '\0';
                    strlcpy(mac, buffer + start, sizeof(mac));
                    buffer[end] = saved;
                    found = 1;
                }
            }
        }

        // If we found a MAC address, add it to disassoc_macs array (avoiding duplicates)
        if (found && mac[0] != '\0') {
            add_unique_mac(disassoc_macs, &disassoc_mac_count, mac, MAX_MACS);
            char details[SYS_CMD_LEN];
            snprintf(details, sizeof(details), "STA %s disconnected from AP", mac);
            print_event(notif_path, mac, "Unknown", "Disassociation", details, buffer, buffer);
        }
    }

    if (compiled_sta_remove) regfree(&rx_sta_remove);
    if (compiled_disassoc) regfree(&rx_disassoc);
    if (compiled_delete) regfree(&rx_delete);
    rewind(syslog);

    regex_t rx_deauth_sta;
    const char *pat_deauth_sta = "\\[([0-9a-f:]{17})\\][[:space:]]*Received[[:space:]]+Deauth[[:space:]]+with[[:space:]]+reason[[:space:]]+([0-9]+)";
    regcomp(&rx_deauth_sta, pat_deauth_sta, REG_EXTENDED | REG_ICASE);

    regex_t rx_ap_kickout_reason;
    const char *pat_ap_kickout_reason = "sending[[:space:]]+DISASSOC[[:space:]]+to[[:space:]]+([0-9a-f:]{17}),[[:space:]]+mlme[[:space:]]+disassoc[[:space:]]+reason[[:space:]]+([0-9]+)";
    regcomp(&rx_ap_kickout_reason, pat_ap_kickout_reason, REG_EXTENDED | REG_ICASE);

    while (fgets(buffer, sizeof(buffer), syslog) != NULL) {
        regmatch_t m[3];

        if (regexec(&rx_deauth_sta, buffer, 3, m, 0) == 0) {
            char mac[SYS_MAC_LEN];
            char reason_s[16];

            {
                int s = (int)m[1].rm_so, e = (int)m[1].rm_eo;
                char saved = buffer[e];
                buffer[e] = '\0';
                strlcpy(mac, buffer + s, sizeof(mac));
                buffer[e] = saved;
            }

            {
                int s = (int)m[2].rm_so, e = (int)m[2].rm_eo;
                char saved = buffer[e];
                buffer[e] = '\0';
                strlcpy(reason_s, buffer + s, sizeof(reason_s));
                buffer[e] = saved;
            }

            int reason_code = atoi(reason_s);
            const char *desc = lookup_reason(reason_code);

            char details[SYS_CMD_LEN];
            snprintf(details, sizeof(details), "STA initiated disconnect with reason %d: %s", reason_code, (desc ? desc : "Unknown"));

            char link_address[NOTE_MAC_LEN] = "Unknown";
            const char *needle = "Received Deauth with reason";
            char *pos = strstr(buffer, needle);
            if (pos != NULL) {
                
                const char *start = pos - (NOTE_MAC_LEN - 1);
                if (start < buffer) start = buffer;
                size_t span = (size_t)(pos - start);
                if (span > 0) {
                    
                    char saved = *pos;
                    *(char *)pos = '\0';
                    strlcpy(link_address, start, sizeof(link_address));
                    *(char *)pos = saved;
                }
            }

            print_event(notif_path, mac, link_address, "STA Initiated Disconnection", details, "Received Deauth with reason", buffer);
            continue;
        }

        if (regexec(&rx_ap_kickout_reason, buffer, 3, m, 0) == 0) {
            char mac[SYS_MAC_LEN];
            char reason_s[16];

            {
                int s = (int)m[1].rm_so, e = (int)m[1].rm_eo;
                char saved = buffer[e];
                buffer[e] = '\0';
                strlcpy(mac, buffer + s, sizeof(mac));
                buffer[e] = saved;
            }

            {
                int s = (int)m[2].rm_so, e = (int)m[2].rm_eo;
                char saved = buffer[e];
                buffer[e] = '\0';
                strlcpy(reason_s, buffer + s, sizeof(reason_s));
                buffer[e] = saved;
            }

            char details[SYS_CMD_LEN];
            snprintf(details, sizeof(details), "An external system has issued a command that makes the AP kick out STA %s.", mac);

            char link_address[NOTE_MAC_LEN] = "Unknown";
            const char *link_str = strstr(buffer, "sending DISASSOC to ");
            if (link_str != NULL) {
                link_str += strlen("sending DISASSOC to ");
                
                size_t i = 0;
                while (link_str[i] != '\0' &&
                       link_str[i] != ',' &&
                       link_str[i] != ' ' &&
                       i < (NOTE_MAC_LEN - 1)) {
                    link_address[i] = link_str[i];
                    i++;
                }
                link_address[i] = '\0';
            }

            print_event(notif_path, mac, link_address, "AP Kickout", details, buffer, buffer);
            continue;
        }

        
        if (strstr(buffer, "station kicked out due to excessive retries associd")) {
            for (int i = 0; i < disassoc_mac_count; i++) {
                if (strstr(buffer, disassoc_macs[i])) {
                    char details[SYS_CMD_LEN];
                    snprintf(details, sizeof(details),
                             "AP kick out STA %s due to excessive retries", disassoc_macs[i]);
                    print_event(notif_path, disassoc_macs[i], "Unknown", "AP Kickout", details, buffer, buffer);
                    break;
                }
            }
        }

        
        if (strstr(buffer, "ap_sta_disconnect (STA addr)") && strstr(buffer, "reason=")) {
            for (int i = 0; i < disassoc_mac_count; i++) {
                if (strstr(buffer, disassoc_macs[i])) {
                    print_event(notif_path, disassoc_macs[i], "Unknown", "Fail to Connect",
                                "Hostapd initiated disconnect", "ap_sta_disconnect", buffer);

                    // avoids duplicate macs from being added to fail_connect_mac_count
                    add_unique_mac(fail_connect_macs, &fail_connect_mac_count, disassoc_macs[i], MAX_MACS);
                    break;
                }
            }
        }
    }

    regfree(&rx_deauth_sta);
    regfree(&rx_ap_kickout_reason);
    rewind(syslog);

    const char *deauth_patterns[] = {
        "Deauth[[:space:]]+with[[:space:]]+reason[[:space:]]+[0-9]+",
        "Deauthenticating[[:space:]]+Station[[:space:]].*Reason:[[:space:]].*\\([0-9]+\\)",
        "deauth:[[:space:]]+reason=[0-9]+",
        "deauthenticated[[:space:]].*\\(Reason:[[:space:]][0-9]+=.*\\)",
        "Received[[:space:]]+Deauth[[:space:]]+with[[:space:]]+reason[[:space:]]+\\([0-9]+\\)"
    };
    int num_deauth_patterns = (int)(sizeof(deauth_patterns) / sizeof(deauth_patterns[0]));

    // Compile all patterns once
    regex_t rx_arr[8];
    for (int i = 0; i < num_deauth_patterns; i++) {
        regcomp(&rx_arr[i], deauth_patterns[i], REG_EXTENDED | REG_ICASE);
    }

    while (fgets(buffer, sizeof(buffer), syslog) != NULL) {
        for (int i = 0; i < num_deauth_patterns; i++) {
            regmatch_t m[1];
            if (regexec(&rx_arr[i], buffer, 1, m, 0) == 0) {
                
                char match_text[128];
                int s = (int)m[0].rm_so, e = (int)m[0].rm_eo;
                char saved = buffer[e];
                buffer[e] = '\0';
                strlcpy(match_text, buffer + s, sizeof(match_text));
                buffer[e] = saved;

                print_event(notif_path, "Unknown", "Unknown", "Deauth Reason Codes",
                            "Syslog line contains deauthentication reason code",
                            match_text, buffer);
                break;
            }
        }
    }
    for (int i = 0; i < num_deauth_patterns; i++) {
        regfree(&rx_arr[i]);
    }

    rewind(syslog);

    // Helper function to extract MAC address from a string
    int extract_mac_from_line(const char *line, char *mac_out, size_t mac_out_size) {
        regex_t rx_mac;
        const char *pat_mac = "([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})";
        if (regcomp(&rx_mac, pat_mac, REG_EXTENDED | REG_ICASE) != 0) {
            return 0;
        }
        
        regmatch_t m[2];
        if (regexec(&rx_mac, line, 2, m, 0) == 0) {
            int start = (int)m[1].rm_so;
            int end = (int)m[1].rm_eo;
            if (start >= 0 && end > start && (end - start) < (int)mac_out_size) {
                char saved = line[end];
                ((char*)line)[end] = '\0';
                strlcpy(mac_out, line + start, mac_out_size);
                ((char*)line)[end] = saved;
                regfree(&rx_mac);
                return 1;
            }
        }
        regfree(&rx_mac);
        return 0;
    }

    // Helper function to remove a MAC address from disassoc_macs array
    void remove_mac_from_disassoc_array(char disassoc_macs[][SYS_MAC_LEN], int *disassoc_mac_count, const char *mac_to_remove) {
        for (int i = 0; i < *disassoc_mac_count; i++) {
            if (strncmp(disassoc_macs[i], mac_to_remove, SYS_MAC_LEN) == 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, 
                           "Removing MAC %s from disassoc_macs (found at index %d)\n", 
                           mac_to_remove, i);
                // Shift remaining MACs down
                for (int j = i; j < *disassoc_mac_count - 1; j++) {
                    strlcpy(disassoc_macs[j], disassoc_macs[j + 1], SYS_MAC_LEN);
                }
                (*disassoc_mac_count)--;
                return;
            }
        }
        log_message(LOG_LEVEL_AD_LIB_DEBUG, 
                   "MAC %s not found in disassoc_macs array\n", 
                   mac_to_remove);
    }

    // Store all lines for backward search
    char **all_lines = NULL;
    int line_count = 0;
    int line_capacity = 1000;
    
    all_lines = (char **)malloc(line_capacity * sizeof(char *));
    if (!all_lines) {
        fclose(syslog);
        return 0;
    }
    
    // Read all lines into memory
    while (fgets(buffer, sizeof(buffer), syslog) != NULL) {
        if (line_count >= line_capacity) {
            line_capacity *= 2;
            char **new_lines = (char **)realloc(all_lines, line_capacity * sizeof(char *));
            if (!new_lines) {
                for (int i = 0; i < line_count; i++) free(all_lines[i]);
                free(all_lines);
                fclose(syslog);
                return 0;
            }
            all_lines = new_lines;
        }
        all_lines[line_count] = strdup(buffer);
        if (!all_lines[line_count]) {
            for (int i = 0; i < line_count; i++) free(all_lines[i]);
            free(all_lines);
            fclose(syslog);
            return 0;
        }
        line_count++;
    }

    struct {
        const char *needle;
        const char *meaning;
    } fail_patterns[] = {
        {"SAE: Confirm mismatch", "wrong password"},
        {"the peer count exceeds the configured number", "max clients reached"},
        //{"MLD: Error in max simultaneous links", "MLD capability mismatch"},
        //{"nl80211: key_mgmt_suites", "PMF capability mismatch"},
        {"wrong bssid", "wrong BSSID"},
        {"Dropping Assoc req frame", "MLO Assoc failure"},
        {"Ignore EAPOL-Key with unexpected type", "EAPOL uses WPA-IE instead of RSN IE"},
        {"RSN: AES unwrap failed", "KEY data decryption failure"},
        {"received EAPOL-Key msg", "EAPOL received in wrong state"},
        {"WPA IE from (Re)AssocReq did not match", "WPA IE mismatch"},
        {"invalid MIC in msg", "invalid MIC in M2"},
        {"FT: Failed to parse FT IEs", "Failed to parse FT IEs"},
        {"FT: Invalid MDIE", "Invalid MDIE"},
        {"FT: Invalid FTIE", "Invalid FTIE"},
        {"FT: No PMKID in RSNIE", "PMKID missing in RSNIE"},
        {"FT: Invalid key mgmt", "Invalid AKM or cipher"},
        {"FT: SNonce mismatch", "FT SNONCE mismatch"},
        {"FT: ANonce mismatch", "FT ANONCE mismatch"},
        {"FT: No R0KH-ID subelem", "R0KH missing"},
        {"FT: R0KH-ID mismatch", "R0KH mismatch"},
        {"FT: No R1KH-ID subelem", "R1KH missing"},
        {"FT: Unknown R1KH-ID", "R1KH mismatch"},
        {"FT: No matching PMKR1Name", "PMKR1Name mismatch"},
        {"FT: Invalid MIC in FTIE", "Invalid FTIE MIC"},
        {"FT: Unexpected IE count in MIC", "FTIE MIC element count mismatch"},
        {"FT: FTE indicated RSNXE missing", "RSNX expected but not found"},
        {"FT: No FTIE in FT 4-way", "FTIE not present in M2"},
        {"FT: No MDIE in FT 4-way", "MDIE not present in M2"},
        {"FT: MDIE mismatch", "MDIE mismatch"},
        {"FT: FTIE mismatch", "FTIE mismatch"}
    };
    int num_fail_patterns = (int)(sizeof(fail_patterns) / sizeof(fail_patterns[0]));

    for (int line_idx = 0; line_idx < line_count; line_idx++) {
        for (int i = 0; i < num_fail_patterns; i++) {
            if (strstr(all_lines[line_idx], fail_patterns[i].needle)) {
                char details[SYS_CMD_LEN];
                snprintf(details, sizeof(details),
                         "Fail to Connect: %s", fail_patterns[i].meaning);
                
                char event_mac[SYS_MAC_LEN] = "Unknown";
                
                if (strcmp(fail_patterns[i].needle, "SAE: Confirm mismatch") == 0) {
                    if (parse_mac_for_sae_confirm_mismatch(all_lines, line_idx, event_mac, sizeof(event_mac))) {
                        add_unique_mac(fail_connect_macs, &fail_connect_mac_count, event_mac, MAX_MACS);
                    }
                }
                // Future patterns will have their own if-blocks here

                print_event(notif_path, event_mac, "Unknown", "Fail to Connect",
                            details, fail_patterns[i].needle, all_lines[line_idx]);
                break;
            }
        }
    }

    // Free allocated memory
    for (int i = 0; i < line_count; i++) {
        free(all_lines[i]);
    }
    free(all_lines);

    fclose(syslog);

    for (int i = 0; i < fail_connect_mac_count; i++) {
        remove_mac_from_disassoc_array(disassoc_macs, &disassoc_mac_count, fail_connect_macs[i]);
    }

    log_message(LOG_LEVEL_AD_LIB_DEBUG, "\n=== MAC Address Lists Before Insertion ===\n");
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Disassoc MACs count: %d\n", disassoc_mac_count);
    for (int i = 0; i < disassoc_mac_count; i++) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "  disassoc_macs[%d]: %s\n", i, disassoc_macs[i]);
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Fail Connect MACs count: %d\n", fail_connect_mac_count);
    for (int i = 0; i < fail_connect_mac_count; i++) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "  fail_connect_macs[%d]: %s\n", i, fail_connect_macs[i]);
    }
    
    // --- Combine MAC Lists and Insert into Notification File ---
    char combined_macs[MAX_MACS * 2][SYS_MAC_LEN];
    int combined_mac_count = 0;

    log_message(LOG_LEVEL_AD_LIB_DEBUG, "\n=== Combining MAC Lists ===\n");
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Anomaly type: %d (ANOM_FAIL_CONNECT=%d)\n", anomaly_type, ANOM_FAIL_CONNECT);
    
    // First, add all from disassoc_macs
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Adding disassoc_macs to combined list...\n");
    for (int i = 0; i < disassoc_mac_count; i++) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "  Adding disassoc_macs[%d]: %s\n", i, disassoc_macs[i]);
        add_unique_mac(combined_macs, &combined_mac_count, disassoc_macs[i], MAX_MACS * 2);
    }

    // If the anomaly is fail-to-connect, also add macs from fail_connect_macs
    if (anomaly_type == ANOM_FAIL_CONNECT) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Anomaly type is FAIL_CONNECT - adding fail_connect_macs to combined list...\n");
        for (int i = 0; i < fail_connect_mac_count; i++) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "  Adding fail_connect_macs[%d]: %s\n", i, fail_connect_macs[i]);
            add_unique_mac(combined_macs, &combined_mac_count, fail_connect_macs[i], MAX_MACS * 2);
        }
    } else {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Anomaly type is NOT FAIL_CONNECT - skipping fail_connect_macs\n");
    }

    log_message(LOG_LEVEL_AD_LIB_DEBUG, "\n=== Final Combined MAC List for Insertion ===\n");
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Combined MACs count: %d\n", combined_mac_count);
    for (int i = 0; i < combined_mac_count; i++) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "  combined_macs[%d]: %s\n", i, combined_macs[i]);
    }
    
    // Insert the unified list into the notification file
    if (combined_mac_count > 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "\nCalling fd_insert_disassoc_macs with %d MACs and notif_path: %s\n", 
                   combined_mac_count, notif_path);
        fd_insert_disassoc_macs(notif_path, combined_macs, combined_mac_count);
    } else {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "\nNo MACs to insert - combined_mac_count is 0\n");
    }
    
    return 0;
}
