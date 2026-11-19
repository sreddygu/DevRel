/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#ifndef DEBUGGING_H
#define DEBUGGING_H

#include <stdio.h>
#include <stdint.h>
#include "fault_detection.h"

extern volatile int g_debug_active;

void get_timestamp_str(char *out, size_t out_sz);
void debug_create_new_file(void);
void debug_start(void);
void debug_stop(void);
void debug_rotate_and_send(void);
void log_message(LogLevel level, const char *format, ...);

#endif // DEBUGGING_H
