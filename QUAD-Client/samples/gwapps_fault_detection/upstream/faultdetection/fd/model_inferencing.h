/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#ifndef MODEL_INFERENCING_H
#define MODEL_INFERENCING_H

#include "nwaios_lib.h"
#include "fault_detection.h"

void unload_model(void);
void fd_nwaios_callback(nwaios_callback_msg_id_t msg_id, void *msg_info, void *user_cookie);
void run_inference(float *input_ten, int rad_id);

#endif // MODEL_INFERENCING_H
