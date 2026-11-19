/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <math.h>
#include <sys/time.h>
#include "model_inferencing.h"
#include "fault_detection.h"
#include "debugging.h"
#include "nwaios_lib.h"
#include "postprocess.h"

static int32_t app_id_2g;
static int32_t app_id_5g;
static int32_t app_id_6g;
static struct nwaios_model_ctx *mctx_2g = NULL;
static struct nwaios_model_ctx *mctx_5g = NULL;
static struct nwaios_model_ctx *mctx_6g = NULL;
static float *input_buf_2g = NULL,  *output_buf_2g = NULL;
static float *input_buf_5g = NULL,  *output_buf_5g = NULL;
static float *input_buf_6g = NULL,  *output_buf_6g = NULL;
static size_t input_size_2g = 0, output_size_2g = 0;
static size_t input_size_5g = 0, output_size_5g = 0;
static size_t input_size_6g = 0, output_size_6g = 0;
static int model_loaded_2g = 0, model_loaded_5g = 0, model_loaded_6g = 0;
static int nwaios_initialized = 0;

void unload_model()
{

	if(model_loaded_2g){
	        nwaios_model_unload(app_id_2g);
		model_loaded_2g = 0;
	}
	if(model_loaded_5g){
		nwaios_model_unload(app_id_5g);
		model_loaded_5g = 0;
	}
	if(model_loaded_6g){
		nwaios_model_unload(app_id_6g);
		model_loaded_6g = 0;
	}
	log_message(LOG_LEVEL_AD_LIB_DEBUG,"===========MODEL UNLOADED===========\n");
}

// Callback function for NWAIOS events
void fd_nwaios_callback(nwaios_callback_msg_id_t msg_id, void *msg_info, void *user_cookie) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "NWAIOS callback received: msg_id = %d\n", msg_id);
        
        switch (msg_id) {
        case NWAIOS_CALLBACK_MSG_ID_START_LOCAL_REQUESTS:
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "NWAIOS: Local compute ready\n");
                break;
                
        case NWAIOS_CALLBACK_MSG_ID_START_REMOTE_REQUESTS:
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "NWAIOS: Remote compute ready\n");
                break;
                
        case NWAIOS_CALLBACK_MSG_ID_STOP_REQUESTS:
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "NWAIOS: Stop all requests\n");
                break;
                
        case NWAIOS_CALLBACK_MSG_ID_STOP_LOCAL_REQUESTS:
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "NWAIOS: Stop local requests\n");
                break;
                
        case NWAIOS_CALLBACK_MSG_ID_STOP_REMOTE_REQUESTS:
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "NWAIOS: Stop remote requests\n");
                break;
                
        default:
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "NWAIOS: Unknown callback msg_id = %d\n", msg_id);
                break;
        }
}

static int ensure_nwaios_init(void)
{
        if (nwaios_initialized) return 0;

        // Initialize app_info structure with callback function (mandatory parameter)
        struct nwaios_app_info app_info = {0};
        app_info.user_callback = fd_nwaios_callback;
        
        nwaios_lib_status_t ret = nwaios_lib_init(&app_info);
        if (ret != NWAIOS_LIB_STATUS_SUCCESS) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to initialize nwaios_lib, ret = %d\n", ret);
                sleep(5);
                // Retry once as shown in sample app
                ret = nwaios_lib_init(&app_info);
                if (ret != NWAIOS_LIB_STATUS_SUCCESS) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[RETRY] Failed to initialize nwaios_lib, ret = %d\n", ret);
                        return -1;
                }
        }
        nwaios_initialized = 1;
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "NWAIOS library initialized successfully\n");
        return 0;
}

static int load_model_for_band(int band)
{
        struct nwaios_model_ctx **mctx_pp   = NULL;
        float **in_buf_pp = NULL, **out_buf_pp = NULL;
        size_t *in_size_p = NULL, *out_size_p = NULL;
        int    *loaded_p  = NULL;
        const char *model_suffix = NULL;

        switch (band) {
                case 2:
                        mctx_pp = &mctx_2g; in_buf_pp = &input_buf_2g; out_buf_pp = &output_buf_2g;
                        in_size_p = &input_size_2g; out_size_p = &output_size_2g;
                        loaded_p = &model_loaded_2g; model_suffix = MODEL_2G;
                        break;
                case 5:
                        mctx_pp = &mctx_5g; in_buf_pp = &input_buf_5g; out_buf_pp = &output_buf_5g;
                        in_size_p = &input_size_5g; out_size_p = &output_size_5g;
                        loaded_p = &model_loaded_5g; model_suffix = MODEL_5G;
                        break;
                case 6:
                        mctx_pp = &mctx_6g; in_buf_pp = &input_buf_6g; out_buf_pp = &output_buf_6g;
                        in_size_p = &input_size_6g; out_size_p = &output_size_6g;
                        loaded_p = &model_loaded_6g; model_suffix = MODEL_6G;
                        break;
                default:
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Unknown band %d\n", band);
                        return -1;
        }

        if (*loaded_p) return 0;

        if (ensure_nwaios_init() != 0) return -1;

        struct nwaios_compute compute = {
                .engine   = NWAIOS_COMPUTE_ENGINE_CPU,
                .location = NWAIOS_COMPUTE_LOCATION_IPQ
        };

        // build model cfg
        struct nwaios_model_cfg model_cfg;
        memset(&model_cfg, 0, sizeof(model_cfg));
        snprintf(model_cfg.model_path, sizeof(model_cfg.model_path), "%s%s", MODEL_PATH, model_suffix);
        model_cfg.num_sessions = 1;
        model_cfg.mtype = NWAIOS_MODEL_TYPE_NATIVE;

        struct nwaios_compute_names out_names = {0};
        nwaios_lib_status_t ret = nwaios_get_compute_names(&compute, &out_names);
        if (ret != NWAIOS_LIB_STATUS_SUCCESS || out_names.num_compute == 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to get compute names, ret = %d\n", ret);
                return -1;
        }
        memcpy(model_cfg.compute_name, out_names.name[0], NWAIOS_COMPUTE_NAME_MAX);

        *mctx_pp = NULL;
        ret = nwaios_model_load(&model_cfg, mctx_pp);
        if (ret != NWAIOS_LIB_STATUS_SUCCESS || *mctx_pp == NULL) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Error loading model for %dg, ret = %d\n", band, ret);
                *loaded_p = 0;
                return -1;
        }

        struct nwaios_exec_ctx *ectx = &(*mctx_pp)->ectx[0];
        if (!ectx) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "%dG ectx is NULL\n", band);
                *loaded_p = 0;
                return -1;
        }

        if (ectx->ip_tensor_num == 0 || ectx->ip_tensor[0].buf == NULL) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Input buffer allocation failed for %dg\n", band);
                *loaded_p = 0;
                return -1;
        }
        if (ectx->op_tensor_num == 0 || ectx->op_tensor[0].buf == NULL) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Output buffer allocation failed for %dg\n", band);
                *loaded_p = 0;
                return -1;
        }

        *in_size_p  = ectx->ip_tensor[0].size;
        *out_size_p = ectx->op_tensor[0].size;
        *in_buf_pp  = (float *)ectx->ip_tensor[0].buf;
        *out_buf_pp = (float *)ectx->op_tensor[0].buf;

        *loaded_p = 1;
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "%dG Model loaded successfully! MODEL_ID: %d, input_size: %zu, output_size: %zu\n",
                        band, (*mctx_pp)->model_id, *in_size_p, *out_size_p);
        return 0;
}

void run_inference(float *input_ten, int rad_id) {
        nwaios_lib_status_t ret;
        struct timeval start, stop;
        double dur_seconds = 0.0;
        // static int32_t cur_app_id = 0; // Unused variable removed

        int cur_band = cur_bands[rad_id];
        log_message(LOG_LEVEL_AD_LIB_DEBUG,"Current band during run_inference(): %d\n", cur_band);

        if (load_model_for_band(cur_band) != 0) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "%dG: load_model_for_band failed\n", cur_band);
                return;
        }

        struct nwaios_model_ctx *mctx = NULL;
        float *input_buf  = NULL;
        float *output_buf = NULL;
        size_t input_size = 0, output_size = 0;

        if (cur_band == 2) {
                mctx = mctx_2g; input_buf = input_buf_2g; output_buf = output_buf_2g;
                input_size = input_size_2g; output_size = output_size_2g;
                // cur_app_id = app_id_2g;
        } else if (cur_band == 5) {
                mctx = mctx_5g; input_buf = input_buf_5g; output_buf = output_buf_5g;
                input_size = input_size_5g; output_size = output_size_5g;
                // cur_app_id = app_id_5g;
        } else if (cur_band == 6) {
                mctx = mctx_6g; input_buf = input_buf_6g; output_buf = output_buf_6g;
                input_size = input_size_6g; output_size = output_size_6g;
                // cur_app_id = app_id_6g;
        } else {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Unsupported band: %d\n", cur_band);
                return;
        }

        if (!mctx) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "%dG: mctx is NULL\n", cur_band);
                return;
        }

        size_t n_model = input_size / sizeof(float);
        if (n_model < MODEL_VEC_LEN) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "%dG: model input buffer too small (%zu floats) < %d\n", cur_band, n_model, MODEL_VEC_LEN);
                return;
        }

        for (size_t i = 0; i < MODEL_VEC_LEN; ++i) {
                input_buf[i] = input_ten[i];
        }

        if (debug_lvl == 1) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "==%dG AI execute model==\n", cur_band);
        }

        gettimeofday(&start, NULL);

        struct nwaios_exec_ctx *ectx = &mctx->ectx[0];
        ret = nwaios_execute(mctx->model_id, ectx->exec_id);
        if (ret) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "%dG nwaios_execute failed! ret: %d\n", cur_band, ret);
                return;
        }

        gettimeofday(&stop, NULL);
        dur_seconds = (double)(stop.tv_usec - start.tv_usec) / 1000000.0
                        + (double)(stop.tv_sec - start.tv_sec);

        if (debug_lvl == 1) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "===========%dG inference duration %.6f s===========\n", cur_band, dur_seconds);
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "==%dG AI execute model done=%d==\n", cur_band, ret);

                size_t out_floats = output_size / sizeof(float);
                for (size_t i = 0; i < out_floats; i++) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, " %zu, \t%.6f\n", i, output_buf[i]);
                }
        }

        process_output(input_ten, output_buf, cur_band, rad_id);
}
