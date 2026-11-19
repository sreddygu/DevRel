/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#ifndef POSTPROCESS_H
#define POSTPROCESS_H

#include "fault_detection.h"

extern float g_last_client_change;
extern float g_last_tx_mgmt_12;
extern float g_last_rx_mgmt_12;

// load the threshold values
typedef struct {
    float beacon_fail_rate_threshold;
    float data_retry_pct_threshold;
    float tx1_tx11_threshold;
    float rx0_rx11_threshold;
    float tx1_rx0_threshold;
    float tx11_rx11_threshold;
    float m1_success_rate_pro_threshold;
    float m3_success_rate_pro_threshold;
    float m1_m3_rate_threshold;
    int is_tx12_or_rx12_active_and_tx1_and_tx3_and_m3_success_inactive_threshold;
    int is_tx12_or_rx12_active_and_tx1_active_threshold;
    float total_clients_threshold;
} Thresholds;

Thresholds load_thresholds(int cur_band, const char *anomaly_type);
void process_output(float *input, float *output, int cur_band, int rad_id);

#endif // POSTPROCESS_H
