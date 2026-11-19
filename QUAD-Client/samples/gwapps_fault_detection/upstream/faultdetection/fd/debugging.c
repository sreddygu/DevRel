/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdarg.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <linux/limits.h>
#include "debugging.h"
#include "peer_stats.h"
#include "transport_client.h"

volatile int g_debug_active = 0;
static char g_debug_file_path[PATH_MAX] = {0};
static FILE *g_debug_fp = NULL;

void get_timestamp_str(char *out, size_t out_sz) {
    time_t now = time(NULL);
    struct tm tm_local;
    localtime_r(&now, &tm_local);
    strftime(out, out_sz, "%Y%m%d_%H%M%S", &tm_local);
}

void debug_create_new_file(void) {
    char ts[32];
    get_timestamp_str(ts, sizeof(ts));
    snprintf(g_debug_file_path, sizeof(g_debug_file_path), "%sdebug_%s.txt", log_dir, ts);
    g_debug_fp = fopen(g_debug_file_path, "w");
    if (g_debug_fp) {
        fprintf(g_debug_fp, "== Debug session started: %s ==\n", ts);
        fflush(g_debug_fp);
    }
}

void debug_start(void) {
    if (g_debug_fp) { fclose(g_debug_fp); g_debug_fp = NULL; }
    if (g_debug_file_path[0]) { remove(g_debug_file_path); g_debug_file_path[0] = '\0'; }

    g_debug_active  = 1;
    debug_create_new_file();

    // Share the file pointer with peer_stats so both use the same file
    peer_stats_set_debug_file_ptr(&g_debug_fp);
    peer_stats_enable_debug();
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Enabled peer_stats debug logging (shared file pointer)\n");
}

void debug_stop(void) {
    // Disable peer_stats debug logging first
    peer_stats_disable_debug();
    log_message(LOG_LEVEL_AD_LIB_DEBUG, "Disabled peer_stats debug logging\n");
    
    g_debug_active  = 0;
    if (g_debug_fp) { fclose(g_debug_fp); g_debug_fp = NULL; }
    if (g_debug_file_path[0]) {
        remove(g_debug_file_path);
        g_debug_file_path[0] = '\0';
    }
}

void debug_rotate_and_send(void) {
    if (!g_debug_active) return;

    if (!g_debug_fp && g_debug_file_path[0] == '\0') {
        debug_create_new_file();
        return;
    }

    if (g_debug_fp) {
        fflush(g_debug_fp);
        fclose(g_debug_fp);
        g_debug_fp = NULL;
    }

    if (g_debug_file_path[0] != '\0') {

        FILE *fp = fopen(g_debug_file_path, "rb");
        if (fp) {
            if (fseek(fp, 0, SEEK_END) == 0) {
                long fsz = ftell(fp);
                if (fsz > 0) {
                    rewind(fp);
                    char *buf = (char*)malloc((size_t)fsz);
                    if (buf) {
                        size_t rd = fread(buf, 1, (size_t)fsz, fp);
                        if (rd == (size_t)fsz) {
                            // Always route DebugLogs via CIA
                            // Build cloud_meta_data for CIA (matching send_logs_to_cloud_for pattern)
                            const char* service_name = "DebugLogs";
                            char name[32] = {0};
                            strlcpy(name, service_name, sizeof(name));

                            bool read_files = false;
                            uint8_t number_of_files = 0;

                            // Calculate cloud_meta_data size
                            /* V2 fields: headerLen + headerVersion + nextHeaderEnum
                             * (no files_size since read_files = false) */
                            size_t cloud_len = 32 + sizeof(bool) + sizeof(uint8_t)
                                               + sizeof(uint16_t) * 3;

                            // Allocate and build cloud_meta_data buffer
                            char *cloud_meta = (char *)malloc(cloud_len);
                            if (!cloud_meta) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "debug_rotate_and_send: malloc failed for cloud_meta\n");
                                free(buf);
                                fclose(fp);
                                remove(g_debug_file_path);
                                g_debug_file_path[0] = '\0';
                                debug_create_new_file();
                                return;
                            }

                            char *p = cloud_meta;
                            
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
                            uint16_t dbg_hdr_len = (uint16_t)cloud_len;
                            memcpy(p, &dbg_hdr_len, sizeof(uint16_t));
                            p += sizeof(uint16_t);
                            uint16_t dbg_hdr_ver = 2;
                            memcpy(p, &dbg_hdr_ver, sizeof(uint16_t));
                            p += sizeof(uint16_t);
                            uint16_t dbg_next_hdr = 0;
                            memcpy(p, &dbg_next_hdr, sizeof(uint16_t));

                            // Build complete message: [cloud_meta_data][debug log content]
                            size_t total_len = cloud_len + (size_t)fsz;
                            char *complete_msg = (char *)malloc(total_len);
                            if (!complete_msg) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "debug_rotate_and_send: malloc failed for complete_msg\n");
                                free(cloud_meta);
                                free(buf);
                                fclose(fp);
                                remove(g_debug_file_path);
                                g_debug_file_path[0] = '\0';
                                debug_create_new_file();
                                return;
                            }

                            memcpy(complete_msg, cloud_meta, cloud_len);
                            memcpy(complete_msg + cloud_len, buf, (size_t)fsz);

                            send_on_channel(APPID_ANAMOLY_DETECTION, APPID_CIA, INPUT_PARAMS, MSG_TYPE_DATA, complete_msg, (int)total_len);
                            
                            log_message(LOG_LEVEL_AD_LIB_DEBUG, "debug_rotate_and_send: sent %zu bytes (cloud_meta: %zu + debug logs: %ld) to CIA\n", 
                                        total_len, cloud_len, fsz);

                            free(complete_msg);
                            free(cloud_meta);
                        }
                        free(buf);
                    }
                }
            }
            fclose(fp);
        }

        remove(g_debug_file_path);
        g_debug_file_path[0] = '\0';
    }

    debug_create_new_file();
}

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

    if (g_debug_active) {
        if (!g_debug_fp) {

            debug_create_new_file();
        }
        if (g_debug_fp) {
            va_list args2;
            va_start(args2, format);
            fprintf(g_debug_fp, "[%s] [%s] ", time_str, level_strings[level]);
            vfprintf(g_debug_fp, format, args2);
            fprintf(g_debug_fp, "\n");
            fflush(g_debug_fp);
            va_end(args2);
        }
    }
}
