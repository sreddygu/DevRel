/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#ifndef PREPROCESS_H
#define PREPROCESS_H

#include "fault_detection.h"

int get_file_length(const char *filename);
void load_values(const char *filename, float *array, int len);
float normalize(int band, float val, int index);
void pre_process(int radio_cnt, float * all_stats, int interval);

#endif // PREPROCESS_H
