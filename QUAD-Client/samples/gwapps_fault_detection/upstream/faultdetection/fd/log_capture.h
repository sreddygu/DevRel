/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#ifndef LOG_CAPTURE_H
#define LOG_CAPTURE_H

#include <stdio.h>
#include <stdlib.h>
#include "fault_detection.h"

int start_pkt_log();
int capture_wifistats_to_file(int rad_id, const char *output_path, int pkt_log);
int save_syslog(const char *notif_path);
void reset_syslog(void);
int save_syslog_usb(const char *notif_path);
void reset_syslog_usb(void);
void check_and_reset_syslog_if_needed(void);

#endif // LOG_CAPTURE_H
