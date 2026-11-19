/*
 * stc_classifier — turnkey module API
 *
 * Implements the third concern of the AI Gateway architecture:
 *   feature extraction → inferencing → **turnkey**
 *
 * Turnkey is the action stage. Examples from the architecture:
 *   - Flow prioritization (mark a TCP flow as high-priority via NSS)
 *   - Power reduction (enable a low-power mode on the radio)
 *   - Channel change (move the AP to a different RF channel)
 *   - Flag a peer for further inspection
 *   - Push a notification to the cloud or a stakeholder app
 *
 * The turnkey can be self-contained (this file does the action) or
 * delegated (this file calls into a stakeholder app or driver).
 */

#ifndef TURNKEY_H
#define TURNKEY_H

#include <stdint.h>

/* Inference outcome passed from postprocess (consume_outputs) into
 * turnkey_act. Extend with your app's domain shape — anomaly score,
 * classified label index, regression value, etc.
 *
 * Keep it POD so it can cross module boundaries cheaply and survive
 * a future move into shared memory if turnkey ever becomes a
 * separate process. */
typedef struct {
    /* Did the model produce a meaningful result this iteration?
     * Set to 0 in postprocess to skip turnkey for this round. */
    int  valid;

    /* App-specific scalar — anomaly score, classification confidence,
     * regression target, etc. Keep semantics in postprocess.c. */
    float score;

    /* Optional integer label / class id. */
    int32_t label;

    /* Reserved for future expansion. */
    uint32_t reserved[4];
} decision_t;

/* Initialize turnkey state — open any IPC handles, load config, etc.
 * Called once at app startup. Returns 0 on success. */
int turnkey_init(void);

/* Act on the decision produced by postprocess.
 *
 * This scaffold is a no-op log + return. Replace with the real action
 * for your app — e.g. push a TCM rule via the NSS wrapper, post an
 * MQTT message via cia_services, write a debug record to syslog, or
 * call into another gwapps app over transport_lib. Returns 0 on
 * success, non-zero on action failure (the main loop will log it but
 * keep running — turnkey failures are not fatal). */
int turnkey_act(const decision_t *decision);

/* Tear down turnkey resources. Called once at app shutdown. */
void turnkey_shutdown(void);

#endif /* TURNKEY_H */
