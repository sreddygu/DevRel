/*
 * stc_classifier — model_inferencing module API
 *
 * One module per inference flow. Production apps that load multiple
 * models (e.g. one per WLAN band as in the fault-detection
 * reference) instantiate this surface multiple times or extend it
 * to take a band/model_id parameter.
 */

#ifndef MODEL_INFERENCING_H
#define MODEL_INFERENCING_H

#include <stdint.h>
#include "nwaios/nwaios_lib.h"

/* Initialize NWAIOS, verify compute engine is reachable, and load
 * the model. Idempotent. Returns 0 on success, non-zero on failure
 * (with diagnostics already written to stderr).
 */
int model_inferencing_init(void);

/* The opaque NWAIOS model context, or NULL before init. Callers
 * use this to access ``inputs[]`` / ``outputs[]`` for the I/O
 * pipeline (see preprocess.c / postprocess.c if you split those
 * out further).
 */
struct nwaios_model_ctx *model_inferencing_ctx(void);

/* Execute one inference pass. ``execute_id`` is the per-context id
 * NWAIOS uses to track multiple concurrent execute streams (today
 * NWAIOS_EXEC_SESSION_MAX = 1, so 0 is the only valid value).
 */
int model_inferencing_run(uint8_t execute_id);

/* Read aggregated stats. Caller-allocated. Returns 0 on success. */
int model_inferencing_stats(struct nwaios_app_stats *out_stats);

/* Unload + lib_deinit. Safe to call multiple times. */
void model_inferencing_shutdown(void);

#endif /* MODEL_INFERENCING_H */
