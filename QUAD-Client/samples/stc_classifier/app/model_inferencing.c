/*
 * stc_classifier — model_inferencing module
 *
 * Encapsulates the NWAIOS lifecycle: lib_init / model_load / execute /
 * unload / lib_deinit + the async callback handler. Keeping it in its
 * own module follows the production reference pattern (see
 * QUAD-Client/samples/gwapps_fault_detection/upstream/faultdetection/
 * fd/model_inferencing.c) so the user can swap inference logic
 * without touching main.c.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "model_inferencing.h"

#define APP_NAME              "stc_classifier"
#define MODEL_PATH            "/var/run/nwaios/stc_classifier/m.bin"
#define COMPUTE_ENGINE        "aim_htp"

/* Single-model state. Real apps may load multiple models (the
 * reference fault-detection app loads one per WLAN band) — extend
 * this module with parallel arrays or per-model structs as needed. */
static int                          g_initialized = 0;
static struct nwaios_model_ctx     *g_mctx = NULL;

/* Async callback. NWAIOS calls this on compute available/unavailable,
 * request start/stop, and reinit. */
static void on_nwaios_event(nwaios_callback_msg_id_t msg_id, void *payload)
{
    (void)payload;
    switch (msg_id) {
        case NWAIOS_CALLBACK_MSG_ID_START_LOCAL_REQUESTS:
            fprintf(stderr, "[%s] compute available\n", APP_NAME);
            break;
        case NWAIOS_CALLBACK_MSG_ID_STOP_LOCAL_REQUESTS:
            fprintf(stderr, "[%s] compute unavailable\n", APP_NAME);
            break;
        case NWAIOS_CALLBACK_MSG_ID_STOP_REQUESTS:
            fprintf(stderr, "[%s] lib reinit requested\n", APP_NAME);
            break;
        default:
            break;
    }
}

static int compute_engine_available(const char *name)
{
    struct nwaios_compute compute[NWAIOS_COMPUTE_MAX];
    uint8_t count = 0;
    nwaios_lib_status_t st = nwaios_get_compute_names(compute, &count);
    if (st != NWAIOS_OK) {
        fprintf(stderr, "[%s] nwaios_get_compute_names failed: %d\n", APP_NAME, st);
        return 0;
    }
    for (uint8_t i = 0; i < count; ++i) {
        if (strncmp(compute[i].name, name, NWAIOS_COMPUTE_NAME_MAX) == 0) {
            return 1;
        }
    }
    fprintf(stderr, "[%s] compute engine '%s' not available; have:", APP_NAME, name);
    for (uint8_t i = 0; i < count; ++i) {
        fprintf(stderr, " %s", compute[i].name);
    }
    fprintf(stderr, "\n");
    return 0;
}

int model_inferencing_init(void)
{
    if (g_initialized) {
        return 0;
    }
    struct nwaios_app_info app_info;
    memset(&app_info, 0, sizeof(app_info));
    strncpy(app_info.name, APP_NAME, sizeof(app_info.name) - 1);
    app_info.client_callback = on_nwaios_event;

    nwaios_lib_status_t st = nwaios_lib_init(&app_info);
    if (st != NWAIOS_OK) {
        fprintf(stderr, "[%s] nwaios_lib_init failed: %d\n", APP_NAME, st);
        return -1;
    }

    if (!compute_engine_available(COMPUTE_ENGINE)) {
        nwaios_lib_deinit();
        return -1;
    }

    struct nwaios_model_cfg cfg;
    memset(&cfg, 0, sizeof(cfg));
    strncpy(cfg.path, MODEL_PATH, sizeof(cfg.path) - 1);
    strncpy(cfg.compute_engine, COMPUTE_ENGINE, sizeof(cfg.compute_engine) - 1);
    cfg.sessions = 1;

    st = nwaios_model_load(&cfg, &g_mctx);
    if (st != NWAIOS_OK || g_mctx == NULL) {
        fprintf(stderr, "[%s] nwaios_model_load failed: %d\n", APP_NAME, st);
        nwaios_lib_deinit();
        return -1;
    }
    fprintf(stderr, "[%s] model loaded id=%u path=%s engine=%s\n",
            APP_NAME, g_mctx->model_id, MODEL_PATH, COMPUTE_ENGINE);

    g_initialized = 1;
    return 0;
}

struct nwaios_model_ctx *model_inferencing_ctx(void)
{
    return g_initialized ? g_mctx : NULL;
}

int model_inferencing_run(uint8_t execute_id)
{
    if (!g_initialized || g_mctx == NULL) {
        return -1;
    }
    nwaios_lib_status_t st = nwaios_execute(g_mctx->model_id, execute_id);
    if (st != NWAIOS_OK) {
        fprintf(stderr, "[%s] nwaios_execute(id=%u) failed: %d\n",
                APP_NAME, g_mctx->model_id, st);
        return -1;
    }
    return 0;
}

int model_inferencing_stats(struct nwaios_app_stats *out_stats)
{
    if (!g_initialized || out_stats == NULL) {
        return -1;
    }
    return (nwaios_get_stats(out_stats) == NWAIOS_OK) ? 0 : -1;
}

void model_inferencing_shutdown(void)
{
    if (g_initialized && g_mctx != NULL) {
        nwaios_model_unload(g_mctx->model_id);
        g_mctx = NULL;
    }
    if (g_initialized) {
        nwaios_lib_deinit();
        g_initialized = 0;
    }
}
