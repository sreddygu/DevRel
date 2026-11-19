/*
 * mobilenetv2 — tensor I/O helpers
 *
 * Phase-3 scaffold: minimal placeholder implementations that fill input
 * tensors with a deterministic pattern and discard outputs. Replace
 * prepare_inputs() and consume_outputs() with your app-specific data
 * pipeline before shipping.
 *
 * The NWAIOS library owns the actual tensor buffers; we only see the
 * model context and read/write through nwaios_model_ctx.inputs[] /
 * .outputs[] (filled by the framework on model_load).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "nwaios/nwaios_lib.h"

/*
 * Fill input tensors before each nwaios_execute().
 *
 * Returns 0 on success, non-zero on error (caller will abort the loop).
 * The default implementation writes a deterministic byte pattern so the
 * generated app runs end-to-end against the mock without a real data
 * source.
 */
int prepare_inputs(struct nwaios_model_ctx *mctx)
{
    if (mctx == NULL) {
        return -1;
    }
    /* Walk the inputs declared on the model context (filled by NWAIOS
     * during model_load) and write a deterministic pattern. Real apps
     * replace this with a frame from a camera, packet from sniffer,
     * sensor reading, etc. */
    for (uint8_t i = 0; i < NWAIOS_TENSOR_MAX; ++i) {
        struct nwaios_tensor *t = &mctx->inputs[i];
        if (t->name[0] == '\0' || t->size == 0 || t->buffer == NULL) {
            continue;
        }
        unsigned char *buf = (unsigned char *)t->buffer;
        for (uint32_t j = 0; j < t->size; ++j) {
            buf[j] = (unsigned char)((i * 31 + j) & 0xFF);
        }
    }
    return 0;
}

/*
 * Consume output tensors after each nwaios_execute().
 *
 * Returns 0 on success. Default: print a one-line digest per output
 * tensor (first 8 bytes as hex). Real apps decode classes / boxes /
 * embeddings here.
 */
int consume_outputs(struct nwaios_model_ctx *mctx)
{
    if (mctx == NULL) {
        return -1;
    }
    for (uint8_t i = 0; i < NWAIOS_TENSOR_MAX; ++i) {
        struct nwaios_tensor *t = &mctx->outputs[i];
        if (t->name[0] == '\0' || t->size == 0 || t->buffer == NULL) {
            continue;
        }
        unsigned char *buf = (unsigned char *)t->buffer;
        uint32_t n = (t->size < 8u) ? t->size : 8u;
        fprintf(stderr, "  out[%s] size=%u first=", t->name, t->size);
        for (uint32_t j = 0; j < n; ++j) {
            fprintf(stderr, "%02x", buf[j]);
        }
        fprintf(stderr, "\n");
    }
    return 0;
}
