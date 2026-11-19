/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#ifndef NOTIFICATION_PROCESSING_H
#define NOTIFICATION_PROCESSING_H

#include "fault_detection.h"
#include "syslog_processing.h"

int delete_dir(char *path);
int create_log_dir(int anomaly_cnt, char* stamp);
int fd_insert_disassoc_macs(const char *notif_path, char disassoc_macs[][SYS_MAC_LEN], int mac_count);
void fd_build_anomaly_log_path(char *out, size_t out_sz);

#endif // NOTIFICATION_PROCESSING_H
