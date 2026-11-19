/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include "notification_processing.h"
#include "debugging.h"

int delete_dir(char *path)
{
        char cmd[CMD_LEN];
        FILE *host_cmd;

        strlcpy(cmd, DEL_CMD, CMD_LEN);
        strlcat(cmd, path, CMD_LEN);
        strlcat(cmd, WILD, CMD_LEN);
        host_cmd = popen(cmd, "r");
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"CMD:%s\n", cmd);
        if(host_cmd == NULL){
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"could Not run delete command\n");
                return -1;
        }
        if(host_cmd) pclose(host_cmd);
        return 0;
}

int create_log_dir(int anomaly_cnt, char* stamp)
{
        char cmd[CMD_LEN];
        char anomaly_str[INT_STR];
        FILE *host_cmd;

        snprintf(anomaly_str, INT_STR, "%d", anomaly_cnt);
        strlcpy(log_folder, log_dir, CMD_LEN);
        strlcat(log_folder, "fd_logs_", CMD_LEN);
        strlcat(log_folder, anomaly_str, CMD_LEN);
        strlcat(log_folder, UNDR_SCR, CMD_LEN);
        delete_dir(log_folder);
        strlcat(log_folder, stamp, CMD_LEN);
        strlcpy(cmd, DIR_CMD, CMD_LEN);
        strlcat(cmd, log_folder, CMD_LEN);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"CMD:%s\n", cmd);
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Logs saved here: %s\n", log_folder);
        host_cmd = popen(cmd, "r");
        if(host_cmd == NULL){
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"could Not run mkdir command\n");
                return -1;
        }
        if(host_cmd) pclose(host_cmd);
        return 0;
}

int fd_insert_disassoc_macs(const char *notif_path, char disassoc_macs[][SYS_MAC_LEN], int mac_count)
{
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "=== fd_insert_disassoc_macs START ===\n");
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "fd_insert_disassoc_macs called with notif_path: %s, mac_count: %d\n", notif_path, mac_count);
    
    if (!notif_path || !notif_path[0]) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "fd_insert_disassoc_macs: notif_path is NULL or empty, returning.\n");
        return 0;
    }

    // Log all MAC addresses being processed
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "MAC addresses to insert:\n");
    for (int i = 0; i < mac_count; i++) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "  [%d]: %s\n", i, disassoc_macs[i]);
    }

    // separate the mac addresses with commas
    char mac_list_str[2048] = {0};
    for (int i = 0; i < mac_count; ++i) {
        if (i) strlcat(mac_list_str, ", ", sizeof(mac_list_str));
        strlcat(mac_list_str, disassoc_macs[i], sizeof(mac_list_str));
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Constructed MAC list string: '%s'\n", mac_list_str);

    // add this line before the Timestamp line
    FILE *nf = fopen(notif_path, "rb");
    if (!nf) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to open notification file '%s' for reading.\n", notif_path);
        return mac_count;
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Successfully opened notification file for reading.\n");

    if (fseek(nf, 0, SEEK_END) != 0) { 
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to seek to end of file.\n");
        fclose(nf); 
        return mac_count; 
    }
    long fsz = ftell(nf);
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "File size: %ld bytes\n", fsz);
    
    if (fsz <= 0 || fsz > (32L * 1024L * 1024L)) { 
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "File size out of bounds (fsz=%ld).\n", fsz);
        fclose(nf); 
        return mac_count; 
    }
    rewind(nf);

    char *buf = (char*)malloc((size_t)fsz + 1);
    if (!buf) { 
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to allocate buffer for file content.\n");
        fclose(nf); 
        return mac_count; 
    }
    size_t rd = fread(buf, 1, (size_t)fsz, nf);
    buf[rd] = '\0';
    fclose(nf); nf = NULL;
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Read %zu bytes from file.\n", rd);

    // Check if MAC addresses already exist in the file
    if (strstr(buf, "Mac Address(es): ") != NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "File already contains 'Mac Address(es): ' - skipping insertion to avoid duplicates.\n");
        free(buf);
        return mac_count;
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "No existing 'Mac Address(es): ' found in file - proceeding with insertion.\n");

    const char *needle_nl = "\nTimestamp:";
    const char *needle    = "Timestamp:";
    char *pos = strstr(buf, needle_nl);
    if (!pos) pos = strstr(buf, needle);

    if (pos) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Found 'Timestamp:' marker in file at position %ld\n", (long)(pos - buf));
    } else {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "No 'Timestamp:' marker found - will insert after first line\n");
    }

    char line_to_insert[4096];
    snprintf(line_to_insert, sizeof(line_to_insert),
             "Mac Address(es): %s\n", (mac_list_str[0] ? mac_list_str : "None"));
    size_t ins_len = strlen(line_to_insert);
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Line to insert: '%s' (length: %zu)\n", line_to_insert, ins_len);

    size_t prefix_len = 0;
    size_t new_len = 0;
    char *newbuf = NULL;

    if (pos) {
        prefix_len = (size_t)(pos - buf);
        new_len = rd + ins_len;
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Inserting before Timestamp: prefix_len=%zu, new_len=%zu\n", prefix_len, new_len);
        newbuf = (char*)malloc(new_len + 1);
        if (newbuf) {
            memcpy(newbuf, buf, prefix_len);
            memcpy(newbuf + prefix_len, line_to_insert, ins_len);
            memcpy(newbuf + prefix_len + ins_len, buf + prefix_len, rd - prefix_len);
            newbuf[new_len] = '\0';
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Successfully constructed new buffer with MAC addresses\n");
        } else {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to allocate newbuf for Timestamp insertion\n");
        }
    } else {
        // if there's no timestamp, add it after the first line
        const char *first_nl = strchr(buf, '\n');
        prefix_len = first_nl ? (size_t)(first_nl - buf + 1) : rd;
        new_len = rd + ins_len;
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Inserting after first line: prefix_len=%zu, new_len=%zu\n", prefix_len, new_len);
        newbuf = (char*)malloc(new_len + 1);
        if (newbuf) {
            memcpy(newbuf, buf, prefix_len);
            memcpy(newbuf + prefix_len, line_to_insert, ins_len);
            memcpy(newbuf + prefix_len + ins_len, buf + prefix_len, rd - prefix_len);
            newbuf[new_len] = '\0';
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Successfully constructed new buffer with MAC addresses\n");
        } else {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to allocate newbuf for first-line insertion\n");
        }
    }

    if (newbuf) {
        FILE *out = fopen(notif_path, "wb");
        if (out) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Writing updated content to notification file '%s' (%zu bytes).\n", notif_path, new_len);
            size_t written = fwrite(newbuf, 1, new_len, out);
            fclose(out);
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Successfully wrote %zu bytes to file.\n", written);
        } else {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to open notification file '%s' for writing.\n", notif_path);
        }
        free(newbuf);
    } else {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to allocate memory for new buffer, no changes made to file.\n");
    }
    free(buf);
    
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "=== fd_insert_disassoc_macs END ===\n");
    return mac_count;
}

void fd_build_anomaly_log_path(char *out, size_t out_sz)
{
    char anomaly_str[16];
    int cur_anom_cnt = anomaly_count % effective_max_anomaly_count;

    snprintf(anomaly_str, sizeof(anomaly_str), "%d_", cur_anom_cnt);

    strlcpy(out, log_folder, out_sz);
    strlcat(out, FWD_SLSH, out_sz);
    strlcat(out, anomaly_str, out_sz);
    strlcat(out, FILE_STR, out_sz);
}
