/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#ifndef CIA_SERVICES_H
#define CIA_SERVICES_H

#include <stddef.h>
#include <stdint.h>

// Helper function to parse cloud_meta_data length dynamically
size_t parse_cloud_meta_length(const char* cloud_meta_ptr, size_t available_len);

// Pending upload queue identifiers
#define UPLOAD_QUEUE_REGULAR 0  /* UploadSnapshot tar+json pairs */
#define UPLOAD_QUEUE_TL1     1  /* DataCollection TL1 tars (tar-only) */
#define UPLOAD_QUEUE_LOGSUM  2  /* LogSummarization tars (tar-only) */

// Helper functions for pending upload management (unified across queues)
// An "upload" is a tar file with an optional paired JSON sidecar tracked for
// delete-on-success or FIFO eviction when MAX_PENDING_UPLOADS is reached.
void add_pending_upload(const char *tar_path, const char *json_path, int queue_type);
void remove_pending_upload(const char *tar_path, int queue_type);
void cleanup_pending_upload_on_success(uint32_t http_status, int queue_type);

// TL=1 helper
void send_tl1_sample(int rad_id, int cur_band, const char *model_label, float clients_per_band);

// TL=2 helpers
void tl2_clear_cycle_state_for_band(int band);
void tl2_begin_new_cycle(void);
void send_tl2_result_for(int rad_id, const char* message_id, const char* result, const char* received_label);

// JSON over CIA helper
void send_json_to_cia(const char* service_name, const char* json_str, size_t json_len);

// Cloud log upload
void send_logs_to_cloud_for(const char *folder_path);

#endif // CIA_SERVICES_H
