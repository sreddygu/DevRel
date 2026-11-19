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
#include <sys/wait.h>
#include <sys/stat.h>
#include <errno.h>
#include <libgen.h>
#include <ctype.h>
#include <limits.h>
#include "cia_services.h"
#include "fault_detection.h"
#include "transport_client.h"
#include "log_capture.h"
#include "debugging.h"

// for CIA log upload tracking (tar + optional paired JSON)
#define MAX_PENDING_UPLOADS 10
static char g_pending_tar_paths[MAX_PENDING_UPLOADS][512];
static char g_pending_json_paths[MAX_PENDING_UPLOADS][512];
static int g_pending_tar_count = 0;

// for TL1 data collection tar upload tracking (tar only; JSON slots stay empty)
static char g_pending_tl1_tar_paths[MAX_PENDING_UPLOADS][512];
static char g_pending_tl1_json_paths[MAX_PENDING_UPLOADS][512];
static int g_pending_tl1_tar_count = 0;

// for LogSummarization tar upload tracking (tar only; JSON slots stay empty)
static char g_pending_logsum_tar_paths[MAX_PENDING_UPLOADS][512];
static char g_pending_logsum_json_paths[MAX_PENDING_UPLOADS][512];
static int g_pending_logsum_tar_count = 0;

// Select the {tar, json, count} triple for a given queue_type; default to regular.
static void select_queue(int queue_type,
                         char (**tar_queue_out)[512],
                         char (**json_queue_out)[512],
                         int **count_out) {
    switch (queue_type) {
        case UPLOAD_QUEUE_TL1:
            *tar_queue_out  = g_pending_tl1_tar_paths;
            *json_queue_out = g_pending_tl1_json_paths;
            *count_out      = &g_pending_tl1_tar_count;
            break;
        case UPLOAD_QUEUE_LOGSUM:
            *tar_queue_out  = g_pending_logsum_tar_paths;
            *json_queue_out = g_pending_logsum_json_paths;
            *count_out      = &g_pending_logsum_tar_count;
            break;
        case UPLOAD_QUEUE_REGULAR:
        default:
            *tar_queue_out  = g_pending_tar_paths;
            *json_queue_out = g_pending_json_paths;
            *count_out      = &g_pending_tar_count;
            break;
    }
}

// Helper function to parse cloud_meta_data length dynamically
size_t parse_cloud_meta_length(const char* cloud_meta_ptr, size_t available_len) {
    if (available_len < 32 + sizeof(bool) + sizeof(uint8_t)) {
        return 0; // Not enough data for basic structure
    }

    const char* p = cloud_meta_ptr;

    // Skip service name (32 bytes)
    p += 32;

    // Read read_files flag
    bool read_files;
    memcpy(&read_files, p, sizeof(bool));
    p += sizeof(bool);

    // Read number_of_files
    uint8_t number_of_files;
    memcpy(&number_of_files, p, sizeof(uint8_t));
    p += sizeof(uint8_t);

    size_t consumed = 32 + sizeof(bool) + sizeof(uint8_t);

    // If read_files is true, we need to skip file paths and data types
    if (read_files && number_of_files > 0) {
        // Skip file paths (null-terminated strings)
        for (int i = 0; i < number_of_files; i++) {
            // Find the null terminator
            const char* null_pos = (const char*)memchr(p, '\0', available_len - consumed);
            if (!null_pos) {
                return 0; // Malformed - no null terminator found
            }
            size_t path_len = (size_t)(null_pos - p) + 1; // +1 for null terminator
            p += path_len;
            consumed += path_len;

            if (consumed >= available_len) {
                return 0; // Exceeded buffer
            }
        }

        // Skip data types array
        size_t data_types_size = number_of_files * sizeof(uint32_t); // enum is 4 bytes
        consumed += data_types_size;

        if (consumed > available_len) {
            return 0; // Exceeded buffer
        }
    }

    /* GWApps 1.2 V2: include files_size array + headerLen + headerVersion + nextHeaderEnum
     * if they fit within the available buffer (backward-compatible: older senders omit them). */
    size_t v2_extra = 0;
    if (read_files && number_of_files > 0) {
        v2_extra += (size_t)number_of_files * sizeof(uint32_t); // files_size array
    }
    v2_extra += sizeof(uint16_t) * 3; // headerLen + headerVersion + nextHeaderEnum

    if (consumed + v2_extra <= available_len) {
        consumed += v2_extra;
    }

    return consumed;
}

// Helper functions for pending upload management (unified across three queues).
// An "upload" is a tar file with an optional paired JSON sidecar tracked for
// delete-on-success or FIFO eviction when MAX_PENDING_UPLOADS is reached.
void add_pending_upload(const char *tar_path, const char *json_path, int queue_type) {
    if (!tar_path || tar_path[0] == '\0') return;

    char (*tar_queue)[512]  = NULL;
    char (*json_queue)[512] = NULL;
    int *count = NULL;
    select_queue(queue_type, &tar_queue, &json_queue, &count);

    // If queue is full, delete the oldest tar+json pair to make room
    if (*count >= MAX_PENDING_UPLOADS) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Pending upload queue full (%d/%d), removing oldest: %s (json: %s)\n",
                   *count, MAX_PENDING_UPLOADS, tar_queue[0], json_queue[0][0] ? json_queue[0] : "<none>");

        // Delete the oldest tar file
        if (remove(tar_queue[0]) == 0) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Successfully deleted oldest tar file: %s\n", tar_queue[0]);
        } else {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to delete oldest tar file: %s (error: %s)\n",
                       tar_queue[0], strerror(errno));
        }

        // Delete the paired JSON file if one is tracked
        if (json_queue[0][0] != '\0') {
            if (remove(json_queue[0]) == 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Successfully deleted oldest json file: %s\n", json_queue[0]);
            } else {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to delete oldest json file: %s (error: %s)\n",
                           json_queue[0], strerror(errno));
            }
        }

        // Shift all entries down by one (remove oldest from both queues)
        for (int i = 0; i < *count - 1; i++) {
            strlcpy(tar_queue[i],  tar_queue[i + 1],  512);
            strlcpy(json_queue[i], json_queue[i + 1], 512);
        }
        (*count)--;
        tar_queue[*count][0]  = '\0';
        json_queue[*count][0] = '\0';
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Removed oldest pair from queue (remaining: %d)\n", *count);
    }

    // Add the new pair to the queue
    strlcpy(tar_queue[*count], tar_path, 512);
    if (json_path && json_path[0] != '\0') {
        strlcpy(json_queue[*count], json_path, 512);
    } else {
        json_queue[*count][0] = '\0';
    }
    (*count)++;
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Added pending upload: %s (json: %s, count: %d, queue_type: %d)\n",
                tar_path, (json_path && json_path[0]) ? json_path : "<none>", *count, queue_type);
}

void remove_pending_upload(const char *tar_path, int queue_type) {
    if (!tar_path || tar_path[0] == '\0') return;

    char (*tar_queue)[512]  = NULL;
    char (*json_queue)[512] = NULL;
    int *count = NULL;
    select_queue(queue_type, &tar_queue, &json_queue, &count);

    for (int i = 0; i < *count; i++) {
        if (strcmp(tar_queue[i], tar_path) == 0) {
            // Delete the tar file
            if (remove(tar_path) == 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Successfully deleted tar file: %s\n", tar_path);
            } else {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to delete tar file: %s (error: %s)\n",
                           tar_path, strerror(errno));
            }

            // Delete the paired JSON file (if any)
            if (json_queue[i][0] != '\0') {
                if (remove(json_queue[i]) == 0) {
                    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Successfully deleted json file: %s\n", json_queue[i]);
                } else {
                    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to delete json file: %s (error: %s)\n",
                               json_queue[i], strerror(errno));
                }
            }

            // Shift remaining entries in both arrays in lockstep
            for (int j = i; j < *count - 1; j++) {
                strlcpy(tar_queue[j],  tar_queue[j + 1],  512);
                strlcpy(json_queue[j], json_queue[j + 1], 512);
            }
            (*count)--;
            tar_queue[*count][0]  = '\0';
            json_queue[*count][0] = '\0';
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "Removed pending upload pair: %s (remaining: %d, queue_type: %d)\n",
                       tar_path, *count, queue_type);
            return;
        }
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Tar file not found in pending upload list: %s\n", tar_path);
}

void cleanup_pending_upload_on_success(uint32_t http_status, int queue_type) {
    char (*tar_queue)[512]  = NULL;
    char (*json_queue)[512] = NULL;
    int *count = NULL;
    select_queue(queue_type, &tar_queue, &json_queue, &count);
    (void)json_queue;  // unused here; remove_pending_upload handles JSON

    if (http_status == 200 && *count > 0) {
        // Remove the oldest pending pair (FIFO); remove_pending_upload will also delete the paired JSON
        remove_pending_upload(tar_queue[0], queue_type);
    }
}

// TL=1 helper
void send_tl1_sample(int rad_id, int cur_band, const char *model_label, float clients_per_band) {

    if (debug_lvl == 1) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Entered send_tl1_sample: g_test_level=%d, rad_id=%d", g_test_level, rad_id);
    }
    if (g_test_level != 1) return;

    if (debug_lvl == 1) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Checking rad_id bounds: rad_id=%d, MAX_RADIOS=%d", rad_id, 4);
    }
    if (rad_id < 0 || rad_id >= MAX_RADIOS) return;

    if (debug_lvl == 1) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Checking stats availability: g_last_stats_available[%d]=%d", rad_id, g_last_stats_available[rad_id]);
    }
    if (!g_last_stats_available[rad_id]) return;

    // Generate timestamp for all files
    char timestamp[32];
    time_t now = time(NULL);
    struct tm tm_local;
    localtime_r(&now, &tm_local);
    strftime(timestamp, sizeof(timestamp), "%Y%m%d_%H%M%S", &tm_local);

    char ts_utc[32];
    struct tm tm_utc;
    gmtime_r(&now, &tm_utc);
    strftime(ts_utc, sizeof(ts_utc), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);

    char band_str[8];
    snprintf(band_str, sizeof(band_str), "%dG", cur_band);

    // Build JSON (enough room for 50 floats + fields + clients_per_band)
    const size_t SZ = 8192;
    char *buf = (char *)malloc(SZ);
    if (!buf) {
        if (debug_lvl == 1) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to allocate buffer for TL1 JSON");
        }
        return;
    }

    size_t off = 0;
    off += snprintf(buf + off, SZ - off,
        "{"
          "\"TEST_LEVEL\":\"1\","
          "\"timestamp\":\"%s\","
          "\"band\":\"%s\","
          "\"model_inference_label\":\"%s\","
          "\"test_label\":\"%s\","
          "\"test_name\":\"%s\","
          "\"clients_per_band\":%g,"
          "\"all_stats\":[",
        ts_utc, band_str, (model_label ? model_label : TEST_LABEL_PASS),
        g_test_label, g_test_name, clients_per_band);

    for (int i = 0; i < CRITICAL_STAT_LEN && off < SZ; i++) {
        off += snprintf(buf + off, SZ - off, (i ? ",%g" : "%g"), g_last_stats_per_radio[rad_id][i]);
    }
    if (off < SZ) off += snprintf(buf + off, SZ - off, "]}");

    log_message(LOG_LEVEL_AD_LIB_DEBUG, "TL1 JSON buffer size used: %zu", off);
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "TL1 JSON Payload (first 256 chars): %.256s", buf);

    // Write JSON to temporary file
    char json_path[512];
    snprintf(json_path, sizeof(json_path), "%stl1_sample_%s.json", log_dir, timestamp);
    FILE *json_fp = fopen(json_path, "w");
    if (!json_fp) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_tl1_sample: failed to create JSON file: %s\n", json_path);
        free(buf);
        return;
    }
    fwrite(buf, 1, off, json_fp);
    fclose(json_fp);
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_tl1_sample: wrote JSON to %s\n", json_path);

    // Capture wifistats to file (pkt_log=0 for TL1)
    char wifistats_path[512];
    snprintf(wifistats_path, sizeof(wifistats_path), "%stl1_wifistats_%s.txt", log_dir, timestamp);
    if (capture_wifistats_to_file(rad_id, wifistats_path, 0) != 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_tl1_sample: failed to capture wifistats\n");
        remove(json_path);
        free(buf);
        return;
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_tl1_sample: captured wifistats to %s\n", wifistats_path);

    // Create tar file containing both JSON and wifistats
    char tar_path[512];
    snprintf(tar_path, sizeof(tar_path), "%stl1_data_%s.tar", log_dir, timestamp);
    
    pid_t cpid = fork();
    if (cpid == 0) {
        // Child process: create tar
        execlp("tar", "tar", "-cf", tar_path, "-C", log_dir, 
               basename(json_path), basename(wifistats_path), (char *)NULL);
        _exit(127);
    }
    if (cpid < 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_tl1_sample: fork() failed: %s\n", strerror(errno));
        remove(json_path);
        remove(wifistats_path);
        free(buf);
        return;
    }
    
    int status = 0;
    if (waitpid(cpid, &status, 0) < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_tl1_sample: tar creation failed (status=%d)\n", status);
        remove(json_path);
        remove(wifistats_path);
        free(buf);
        return;
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_tl1_sample: created tar file %s\n", tar_path);

    // Cleanup temporary JSON and wifistats files
    remove(json_path);
    remove(wifistats_path);

    /* GWApps 1.2: get tar file size for V2 files_size field */
    struct stat tar_stat_buf;
    uint32_t tar_file_size = 0;
    if (stat(tar_path, &tar_stat_buf) == 0) {
        tar_file_size = (uint32_t)tar_stat_buf.st_size;
    }

    // Build cloud_meta_data and send to CIA for forwarding via MQTT
    const char* service_name = "DataCollection";
    char name[32] = {0};
    strlcpy(name, service_name, sizeof(name));

    bool read_files = true;
    uint8_t number_of_files = 1;

    enum cloud_data_type {
        JSON = 0,
        TEXT = 1,
        BINARY = 2
    };
    enum cloud_data_type data_type = BINARY;

    size_t cloud_len = 32 + sizeof(bool) + sizeof(uint8_t);
    size_t path_len = strlen(tar_path) + 1;
    cloud_len += path_len;
    cloud_len += sizeof(enum cloud_data_type);
    /* V2 fields: files_size (1 entry) + headerLen + headerVersion + nextHeaderEnum */
    cloud_len += sizeof(uint32_t) + sizeof(uint16_t) * 3;

    char *cloud_meta = (char *)malloc(cloud_len);
    if (!cloud_meta) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_tl1_sample: malloc failed for cloud_meta\n");
        remove(tar_path);
        free(buf);
        return;
    }

    char *p = cloud_meta;
    memcpy(p, name, 32);                              p += 32;
    memcpy(p, &read_files, sizeof(bool));             p += sizeof(bool);
    memcpy(p, &number_of_files, sizeof(uint8_t));     p += sizeof(uint8_t);
    memcpy(p, tar_path, path_len);                    p += path_len;
    memcpy(p, &data_type, sizeof(enum cloud_data_type)); p += sizeof(enum cloud_data_type);
    /* V2 fields */
    memcpy(p, &tar_file_size, sizeof(uint32_t));      p += sizeof(uint32_t);
    uint16_t hdr_len_v = (uint16_t)cloud_len;
    memcpy(p, &hdr_len_v, sizeof(uint16_t));          p += sizeof(uint16_t);
    uint16_t hdr_ver = 2;
    memcpy(p, &hdr_ver, sizeof(uint16_t));            p += sizeof(uint16_t);
    uint16_t next_hdr = 0;
    memcpy(p, &next_hdr, sizeof(uint16_t));

    send_on_channel(APPID_ANAMOLY_DETECTION, APPID_CIA, INPUT_PARAMS, MSG_TYPE_DATA, cloud_meta, (int)cloud_len);

    log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_tl1_sample: sent %zu bytes cloud_meta to CIA for file: %s\n",
                cloud_len, tar_path);

    // Add tar to TL1 queue for cleanup on CIA upload confirmation
    add_pending_upload(tar_path, NULL, UPLOAD_QUEUE_TL1);

    free(cloud_meta);
    free(buf);
}

// JSON over CIA helper
void send_json_to_cia(const char* service_name, const char* json_str, size_t json_len) {
    if (!service_name || !json_str || json_len == 0) return;

    char name[32] = {0};
    strlcpy(name, service_name, sizeof(name));

    bool read_files = false;
    uint8_t number_of_files = 0;

    // Calculate cloud_meta_data size
    /* V2 fields: headerLen + headerVersion + nextHeaderEnum
     * (no files_size since read_files = false) */
    size_t cloud_len = 32 + sizeof(bool) + sizeof(uint8_t) + sizeof(uint16_t) * 3;

    // Allocate and build total message buffer: [cloud_meta][json]
    size_t total_len = cloud_len + json_len;
    char *msg_buf = (char *)malloc(total_len);
    if (!msg_buf) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_json_to_cia: malloc failed\n");
        return;
    }

    char *p = msg_buf;
    
    // Service name (32 bytes, zero-padded)
    memcpy(p, name, 32);
    p += 32;
    
    // read_files flag
    memcpy(p, &read_files, sizeof(bool));
    p += sizeof(bool);
    
    // number_of_files
    memcpy(p, &number_of_files, sizeof(uint8_t));
    p += sizeof(uint8_t);

    // V2 fields (no files_size: read_files == false)
    uint16_t hdr_len_v = (uint16_t)cloud_len;
    memcpy(p, &hdr_len_v, sizeof(uint16_t));
    p += sizeof(uint16_t);
    uint16_t hdr_ver = 2;
    memcpy(p, &hdr_ver, sizeof(uint16_t));
    p += sizeof(uint16_t);
    uint16_t next_hdr = 0;
    memcpy(p, &next_hdr, sizeof(uint16_t));
    p += sizeof(uint16_t);

    // Copy JSON payload
    memcpy(p, json_str, json_len);

    send_on_channel(APPID_ANAMOLY_DETECTION, APPID_CIA, INPUT_PARAMS, MSG_TYPE_DATA, msg_buf, (int)total_len);
    
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_json_to_cia: sent %zu bytes to CIA (%s)\n", total_len, service_name);

    free(msg_buf);
}

// TL=2 helpers
void tl2_clear_cycle_state_for_band(int band) {
    if (band < 0 || band > 6) return;
    // free previous per-band baseline if allocated
    if (g_prev_itr_by_band[band]) {
        free(g_prev_itr_by_band[band]);
        g_prev_itr_by_band[band] = NULL;
    }
    g_prev_cli_by_band[band] = 0;
    g_tl2_seen_first_by_band[band] = 0;
}

void tl2_begin_new_cycle(void) {
    // reset all bands we support
    tl2_clear_cycle_state_for_band(2);
    tl2_clear_cycle_state_for_band(5);
    tl2_clear_cycle_state_for_band(6);
}

void send_tl2_result_for(int rad_id, const char* message_id, const char* result, const char* received_label) {
    if (g_test_level != 2 || !message_id || !message_id[0]) return;

    char ts[32];
    time_t now = time(NULL);
    struct tm tm_utc;
    gmtime_r(&now, &tm_utc);
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);

    char buf[512];
    int n = snprintf(buf, sizeof(buf),
        "{"
          "\"TEST_LEVEL\":\"2\","
          "\"message_id\":\"%s\","
          "\"result\":\"%s\","
          "\"received_label\":\"%s\","
          "\"timestamp\":\"%s\""
        "}",
        message_id,
        (result ? result : ""),
        (received_label ? received_label : ""),
        ts);

    if (n > 0) {
        send_json_to_cia("UnitTest", buf, n);
    }
}

void send_logs_to_cloud_for(const char *folder_path)
{
    if (!folder_path || folder_path[0] == '\0') {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: invalid folder_path\n");
        return;
    }

    /* ---------------------------------------------------------------
     * LogSummarization emission: single {folder_basename}.tar
     * Customer-selectable via CIA's config.json; we always emit both
     * services so either one can be picked up on the CIA side.
     * --------------------------------------------------------------- */
    {
        const char *base_name = strrchr(folder_path, '/');
        base_name = base_name ? base_name + 1 : folder_path;

        char logsum_tar_path[512];
        snprintf(logsum_tar_path, sizeof(logsum_tar_path), "%s%s.tar", log_dir, base_name);

        pid_t ls_cpid = fork();
        if (ls_cpid == 0) {
            execlp("tar", "tar", "-cf", logsum_tar_path, "-C", folder_path, ".", (char *)NULL);
            _exit(127);
        }
        if (ls_cpid < 0) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: LogSummarization fork() failed: %s\n", strerror(errno));
            goto logsum_done;
        }
        int ls_status = 0;
        if (waitpid(ls_cpid, &ls_status, 0) < 0 || !WIFEXITED(ls_status) || WEXITSTATUS(ls_status) != 0) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: LogSummarization tar failed for %s (status=%d)\n",
                        folder_path, ls_status);
            remove(logsum_tar_path);
            goto logsum_done;
        }

        /* GWApps 1.2: tar file size for V2 files_size field */
        struct stat ls_stat_buf;
        uint32_t ls_tar_file_size = 0;
        if (stat(logsum_tar_path, &ls_stat_buf) == 0) {
            ls_tar_file_size = (uint32_t)ls_stat_buf.st_size;
        }

        const char* ls_service_name = "LogSummarization";
        char ls_name[32] = {0};
        strlcpy(ls_name, ls_service_name, sizeof(ls_name));

        bool ls_read_files = true;
        uint8_t ls_number_of_files = 1;

        enum cloud_data_type_ls {
            LS_JSON = 0,
            LS_TEXT = 1,
            LS_BINARY = 2
        };
        enum cloud_data_type_ls ls_data_type = LS_BINARY;

        size_t ls_path_len = strlen(logsum_tar_path) + 1;
        size_t ls_cloud_len = 32 + sizeof(bool) + sizeof(uint8_t);
        ls_cloud_len += ls_path_len;
        ls_cloud_len += sizeof(enum cloud_data_type_ls);
        /* V2 fields: files_size (1 entry) + headerLen + headerVersion + nextHeaderEnum */
        ls_cloud_len += sizeof(uint32_t) + sizeof(uint16_t) * 3;

        char *ls_cloud_meta = (char *)malloc(ls_cloud_len);
        if (!ls_cloud_meta) {
            log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: LogSummarization malloc failed\n");
            remove(logsum_tar_path);
            goto logsum_done;
        }

        char *lp = ls_cloud_meta;
        memcpy(lp, ls_name, 32);                                        lp += 32;
        memcpy(lp, &ls_read_files, sizeof(bool));                       lp += sizeof(bool);
        memcpy(lp, &ls_number_of_files, sizeof(uint8_t));               lp += sizeof(uint8_t);
        memcpy(lp, logsum_tar_path, ls_path_len);                       lp += ls_path_len;
        memcpy(lp, &ls_data_type, sizeof(enum cloud_data_type_ls));     lp += sizeof(enum cloud_data_type_ls);
        /* V2 fields */
        memcpy(lp, &ls_tar_file_size, sizeof(uint32_t));                lp += sizeof(uint32_t);
        uint16_t ls_hdr_len_v = (uint16_t)ls_cloud_len;
        memcpy(lp, &ls_hdr_len_v, sizeof(uint16_t));                    lp += sizeof(uint16_t);
        uint16_t ls_hdr_ver = 2;
        memcpy(lp, &ls_hdr_ver, sizeof(uint16_t));                      lp += sizeof(uint16_t);
        uint16_t ls_next_hdr = 0;
        memcpy(lp, &ls_next_hdr, sizeof(uint16_t));

        send_on_channel(APPID_ANAMOLY_DETECTION, APPID_CIA, INPUT_PARAMS, MSG_TYPE_DATA,
                        ls_cloud_meta, (int)ls_cloud_len);

        add_pending_upload(logsum_tar_path, NULL, UPLOAD_QUEUE_LOGSUM);

        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: sent %zu bytes cloud_meta to CIA for file: %s (LogSummarization)\n",
                    ls_cloud_len, logsum_tar_path);

        free(ls_cloud_meta);
    }
logsum_done:
    ;  /* empty statement so the label is valid under strict C99 */

    /* ---------------------------------------------------------------
     * UploadSnapshot emission: incident tar + incident JSON sidecar
     * --------------------------------------------------------------- */

    // Build incident_id from current timestamp: incident_YYYYMMDDHHMMSS
    char ts[32];
    time_t now = time(NULL);
    struct tm tm_local;
    localtime_r(&now, &tm_local);
    strftime(ts, sizeof(ts), "%Y%m%d%H%M%S", &tm_local);

    char incident_id[64];
    snprintf(incident_id, sizeof(incident_id), "incident_%s", ts);

    // Tar filename carries its own creation-time stamp: {incident_id}_YYYYMMDD_HHMMSS.tar
    char tar_stamp[20];
    time_t t_tar = time(NULL);
    struct tm tm_tar;
    localtime_r(&t_tar, &tm_tar);
    strftime(tar_stamp, sizeof(tar_stamp), "%Y%m%d_%H%M%S", &tm_tar);

    char tar_path[512];
    snprintf(tar_path, sizeof(tar_path), "%s%s_%s.tar", log_dir, incident_id, tar_stamp);

    // Create tar file from folder contents
    pid_t cpid = fork();
    if (cpid == 0) {
        execlp("tar", "tar", "-cf", tar_path, "-C", folder_path, ".", (char *)NULL);
        _exit(127);
    }
    if (cpid < 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: fork() failed: %s\n", strerror(errno));
        return;
    }
    int status = 0;
    if (waitpid(cpid, &status, 0) < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: tar failed for %s (status=%d)\n",
                    folder_path, status);
        remove(tar_path);
        return;
    }

    // JSON filename carries its own creation-time stamp: {incident_id}_YYYYMMDD_HHMMSS.json
    char json_stamp[20];
    time_t t_json = time(NULL);
    struct tm tm_json;
    localtime_r(&t_json, &tm_json);
    strftime(json_stamp, sizeof(json_stamp), "%Y%m%d_%H%M%S", &tm_json);

    char json_path[512];
    snprintf(json_path, sizeof(json_path), "%s%s_%s.json", log_dir, incident_id, json_stamp);

    // Write the incident JSON sidecar (incident_type=CONNECTIVITY)
    FILE *json_fp = fopen(json_path, "w");
    if (!json_fp) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: failed to create json file %s: %s\n",
                    json_path, strerror(errno));
        remove(tar_path);
        return;
    }
    fprintf(json_fp, "{\n");
    fprintf(json_fp, "  \"incident_id\": \"%s\",\n", incident_id);
    fprintf(json_fp, "  \"timestamp\": \"%s\",\n", ts);
    fprintf(json_fp, "  \"incident_type\": \"CONNECTIVITY\",\n");
    fprintf(json_fp, "  \"files\": [\"%s\", \"%s\"],\n", tar_path, json_path);
    fprintf(json_fp, "  \"file_count\": 2\n");
    fprintf(json_fp, "}\n");
    if (fclose(json_fp) != 0) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: failed to close json file %s: %s\n",
                    json_path, strerror(errno));
        remove(tar_path);
        remove(json_path);
        return;
    }

    // Build cloud_meta_data for the pair (matching the UploadSnapshot sample pattern)
    const char* service_name = "UploadSnapshot";
    char name[32] = {0};
    strlcpy(name, service_name, sizeof(name));

    bool read_files = true;
    uint8_t number_of_files = 2;

    enum cloud_data_type {
        JSON = 0,
        TEXT = 1,
        BINARY = 2
    };
    enum cloud_data_type data_types[2] = { BINARY, JSON };

    // GWApps 1.2: per-file sizes for V2 files_size array
    struct stat st;
    uint32_t file_sizes[2] = { 0, 0 };
    if (stat(tar_path,  &st) == 0) file_sizes[0] = (uint32_t)st.st_size;
    if (stat(json_path, &st) == 0) file_sizes[1] = (uint32_t)st.st_size;

    size_t tar_path_len  = strlen(tar_path)  + 1; // +1 for null terminator
    size_t json_path_len = strlen(json_path) + 1;

    size_t cloud_len = sizeof(name) + sizeof(bool) + sizeof(uint8_t);
    cloud_len += tar_path_len + json_path_len;
    cloud_len += sizeof(data_types);
    // V2 fields: files_size (2 entries) + headerLen + headerVersion + nextHeaderEnum
    cloud_len += sizeof(file_sizes) + sizeof(uint16_t) * 3;

    char *cloud_meta = (char *)malloc(cloud_len);
    if (!cloud_meta) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: malloc failed\n");
        remove(tar_path);
        remove(json_path);
        return;
    }

    char *p = cloud_meta;
    memcpy(p, name, sizeof(name));                           p += sizeof(name);
    memcpy(p, &read_files, sizeof(bool));                    p += sizeof(bool);
    memcpy(p, &number_of_files, sizeof(uint8_t));            p += sizeof(uint8_t);
    memcpy(p, tar_path, tar_path_len);                       p += tar_path_len;
    memcpy(p, json_path, json_path_len);                     p += json_path_len;
    memcpy(p, data_types, sizeof(data_types));               p += sizeof(data_types);
    // V2 fields
    memcpy(p, file_sizes, sizeof(file_sizes));               p += sizeof(file_sizes);
    uint16_t hdr_len_v = (uint16_t)cloud_len;
    memcpy(p, &hdr_len_v, sizeof(uint16_t));                 p += sizeof(uint16_t);
    uint16_t hdr_ver = 2;
    memcpy(p, &hdr_ver, sizeof(uint16_t));                   p += sizeof(uint16_t);
    uint16_t next_hdr = 0;
    memcpy(p, &next_hdr, sizeof(uint16_t));

    send_on_channel(APPID_ANAMOLY_DETECTION, APPID_CIA, INPUT_PARAMS, MSG_TYPE_DATA, cloud_meta, (int)cloud_len);

    free(cloud_meta);

    add_pending_upload(tar_path, json_path, UPLOAD_QUEUE_REGULAR);  // UploadSnapshot tar+json pair
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "send_logs_to_cloud_for: sent %zu bytes cloud_meta to CIA for files: %s and %s\n",
                cloud_len, tar_path, json_path);
}
