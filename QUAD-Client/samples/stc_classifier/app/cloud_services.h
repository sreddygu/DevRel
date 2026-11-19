/*
 * stc_classifier — cloud services API
 *
 * Wraps the gwapps Cloud Interface Agent (CIA) for outbound cloud
 * telemetry. Apps publish per-inference stats via this module; the
 * cloud schema follows the formal naming convention:
 *
 *     application_name = "WIN-NW-STC-CLASSIFIER"
 *     model_name       = "WIN-NW-STC-CLASSIFIER-AE-DEFAULT"
 *
 * Per the cloud APIs schema:
 *   - WIN-<TYPE>-<APP>             for application_id
 *   - WIN-<TYPE>-<APP>-<ALGO>-<INFO> for model_id
 *
 * Edit cloud_app_id and cloud_model_id passed to QUAD codegen to
 * match your formal app/model registry entries.
 */

#ifndef CLOUD_SERVICES_H
#define CLOUD_SERVICES_H

#include <stdint.h>

#include "turnkey.h"  /* for decision_t */

/* Initialize CIA session for this app. Idempotent. Returns 0 on
 * success. */
int cloud_services_init(void);

/* Publish a per-inference record to cloud. Honors the cloud schema:
 * application_name + model_name + execution_time + decision_t fields.
 * Returns 0 on success; non-zero failures are logged but won't fail
 * the inference loop (per gwapps app conventions). */
int cloud_services_publish_inference(
    const decision_t *decision,
    uint32_t execution_time_us);

/* Publish per-app aggregate stats (memory, request counts, latency
 * percentiles) on a cadence. Typically called every N seconds. */
int cloud_services_publish_app_stats(void);

/* Tear down the CIA session. */
void cloud_services_shutdown(void);

#endif /* CLOUD_SERVICES_H */
