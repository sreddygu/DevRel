/*
 * stc_classifier -- turnkey module implementation
 *
 * Action: write the classification decision to syslog so it lands in
 * journalctl / logread on the gateway. Real production builds can
 * extend this with NSS flow-priority hooks or netlink-based QoS rules.
 */

#include <stdio.h>
#include <syslog.h>

#include "turnkey.h"
#include "debugging.h"

/* Class-name lookup defined in tensor_io.c. */
extern const char *stc_class_name(int32_t label);

#define SYSLOG_IDENT "stc_classifier"

/* Suppress noisy per-iteration logs when the gateway is steady-state.
 * Only emit a syslog entry on a class transition or every Nth iteration. */
#define STC_SYSLOG_EVERY_N 10

static int32_t  g_last_label = -2;
static uint64_t g_iter_count = 0;

int turnkey_init(void)
{
    openlog(SYSLOG_IDENT, LOG_PID | LOG_CONS, LOG_USER);
    syslog(LOG_INFO, "stc_classifier turnkey ready (5-class STC, syslog sink)");
    LOG_INFO("turnkey_init: syslog opened ident=%s", SYSLOG_IDENT);
    return 0;
}

int turnkey_act(const decision_t *decision)
{
    if (decision == NULL || !decision->valid) {
        LOG_DEBUG("turnkey_act: skipping invalid decision");
        return 0;
    }

    ++g_iter_count;
    int transitioned = (decision->label != g_last_label);
    int periodic = ((g_iter_count % STC_SYSLOG_EVERY_N) == 0);

    if (transitioned || periodic) {
        const char *cls = stc_class_name(decision->label);
        syslog(LOG_INFO,
               "class=%s label=%d confidence=%.3f iter=%llu%s",
               cls,
               decision->label,
               (double)decision->score,
               (unsigned long long)g_iter_count,
               transitioned ? " (transition)" : "");
        g_last_label = decision->label;
    }

    return 0;
}

void turnkey_shutdown(void)
{
    syslog(LOG_INFO, "stc_classifier turnkey shutting down (iter=%llu)",
           (unsigned long long)g_iter_count);
    closelog();
    LOG_INFO("turnkey_shutdown");
}
