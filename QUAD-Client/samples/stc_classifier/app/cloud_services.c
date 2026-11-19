/*
 * stc_classifier — cloud services module (CIA wrapper).
 *
 * Scaffolded — replace the cia_publish() call sites with the actual
 * CIA C API once the gwapps SDK header for CIA is on the include
 * path. The default implementation logs at INFO level and returns 0
 * so the inference loop runs end-to-end without a real cloud
 * connection.
 *
 * The cloud schema follows the formal naming convention from the
 * cloud APIs design doc — see cloud_services.h for the contract.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "cloud_services.h"
#include "debugging.h"

#define CLOUD_APP_ID    "WIN-NW-STC-CLASSIFIER"
#define CLOUD_MODEL_ID  "WIN-NW-STC-CLASSIFIER-AE-DEFAULT"

static int g_cloud_initialized = 0;

int cloud_services_init(void)
{
    if (g_cloud_initialized) {
        return 0;
    }
    /* Real implementation would call:
     *   #include "cia_services.h"
     *   cia_handle_t handle = cia_init(CLOUD_APP_ID, ...);
     * Today this is a no-op stub. */
    LOG_INFO("cloud_services_init: app=%s model=%s (scaffold no-op)",
             CLOUD_APP_ID, CLOUD_MODEL_ID);
    g_cloud_initialized = 1;
    return 0;
}

int cloud_services_publish_inference(
    const decision_t *decision,
    uint32_t execution_time_us)
{
    if (!g_cloud_initialized || decision == NULL) {
        return -1;
    }
    /* Cloud schema fields per the design doc:
     *   application_name        : CLOUD_APP_ID
     *   model_name              : CLOUD_MODEL_ID
     *   model_priority          : (set by daemon, read from app_stats)
     *   execution_time          : execution_time_us / 1000  (ms)
     *   no_of_inferences        : counter (track in this module)
     *   no_of_successful_inference: ditto
     *   feature_stats           : float[] — optional pre-tensor record
     *   input_tensor            : uint32_t[] — last input
     *   output_tensor           : uint32_t[] — last output
     *
     * Real path: marshal the fields into the CIA message format and
     * call cia_publish_message(handle, payload). For now log only. */
    LOG_DEBUG("cloud publish: model=%s label=%d score=%.4f exec=%uus",
              CLOUD_MODEL_ID, decision->label, decision->score,
              execution_time_us);
    return 0;
}

int cloud_services_publish_app_stats(void)
{
    if (!g_cloud_initialized) {
        return -1;
    }
    /* Aggregate AppStats fields per the cloud schema:
     *   application_id, total_memory_usage_kb, num_models_loaded,
     *   avg_inf_aios, avg_n_inf_aios, ap_timestamp_epoch.
     * Source: nwaios_get_stats() / nwaios_app_stats. */
    LOG_DEBUG("cloud publish app stats: app=%s ts=%ld",
              CLOUD_APP_ID, (long)time(NULL));
    return 0;
}

void cloud_services_shutdown(void)
{
    if (!g_cloud_initialized) {
        return;
    }
    LOG_INFO("cloud_services_shutdown");
    /* Real impl: cia_close(handle); */
    g_cloud_initialized = 0;
}
