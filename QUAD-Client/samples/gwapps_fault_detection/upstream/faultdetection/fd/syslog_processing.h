/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#ifndef SYSLOG_PROCESSING_H
#define SYSLOG_PROCESSING_H

#include <stdio.h>
#include <stdarg.h>

/* Logging comes from debugging.h / fault_detection.h; do not redeclare here. */

/*
 * Constants used by syslog parsing/printing. These were historically defined
 * in fault_detection.c; they live here now so syslog_processing.c compiles
 * self-contained.
 */
#define SYS_MAX_LEN 1024

#define SYS_MAC_LEN 18

// #ifndef NOTE_MAC_LEN
#define NOTE_MAC_LEN 20
// #endif

// #ifndef MAX_MACS
#define MAX_MACS 100
// #endif

#define SYS_CMD_LEN 256

#define ANOMALY_VAL_LEN 500

/* Helper implemented in fault_detection.c (used by syslog_processing.c). */
int fd_insert_disassoc_macs(const char *notif_path, char disassoc_macs[][SYS_MAC_LEN], int mac_count);


// ReasonCode structure for WiFi disconnect reasons
typedef struct {
    int code;
    const char *description;
} ReasonCode;

// External declarations for reason code definitions
extern ReasonCode reason_definitions[];
extern const int reason_definitions_count;

// Function declarations
const char* lookup_reason(int code);
int regex_match(const char *pattern, const char *text);
void print_event(const char *notif_path,
                 const char *mac,
                 const char *link_addr,
                 const char *event,
                 const char *details,
                 const char *log_match,
                 const char *line);
int process_syslog(char *sys_path, const char *notif_path, int anomaly_type);
int add_unique_mac(char macs[][SYS_MAC_LEN], int *mac_count, const char *mac, int max_macs);

#endif // SYSLOG_PROCESSING_H
