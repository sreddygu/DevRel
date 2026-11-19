/*
 * stc_classifier -- feature extraction (preprocess + postprocess)
 *
 * STC = Smart Traffic Classifier. 5-class output:
 *   0 = video, 1 = voip, 2 = web, 3 = iot, 4 = bulk
 *
 * Input tensor: [1, 1, 64] float32 -- 64 packet header bytes
 *               normalized to [0, 1]. Real apps replace prepare_inputs
 *               with a libnetfilter_queue / nfq_open + nfq_handle_packet
 *               read of the packet header (Ethernet + IP + TCP/UDP).
 *               This scaffold synthesizes a deterministic header stream
 *               so the app round-trips against the NWAIOS mock without
 *               root + nfqueue setup.
 *
 * Output tensor: [1, 5] float32 -- per-class logits.
 *                consume_outputs runs softmax + argmax and packs the
 *                top class into decision_t.
 */

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "nwaios/nwaios_lib.h"
#include "debugging.h"
#include "turnkey.h"

#define STC_INPUT_LEN  64u   /* 64 packet header bytes */
#define STC_NUM_CLASSES 5u

/* Class names for human-readable logging. Index matches the model
 * output order. Keep in sync with build_model.py and turnkey.c. */
static const char *const STC_CLASS_NAMES[STC_NUM_CLASSES] = {
    "video", "voip", "web", "iot", "bulk",
};

/* Synthetic packet stream state -- bumps on each iteration so the mock
 * exercises a non-trivial input distribution. Production builds replace
 * this with nfq_open() + nfq_handle_packet(). */
static uint64_t g_packet_seq = 0;

/*
 * Fill input tensor with normalized packet header bytes.
 *
 * Production: read 64 bytes from the head of a packet via
 * libnetfilter_queue (or libpcap for monitor mode). Normalize each
 * byte by dividing by 255.0f.
 *
 * This scaffold: derive 64 bytes deterministically from g_packet_seq.
 * Different seq values produce different "packets" so successive
 * inferences see varied input distributions.
 */
int prepare_inputs(struct nwaios_model_ctx *mctx)
{
    if (mctx == NULL) {
        return -1;
    }

    /* The model has a single input tensor of shape [1, 1, 64]. Find it
     * (first non-empty input tensor) and write 64 normalized floats. */
    for (uint8_t i = 0; i < NWAIOS_TENSOR_MAX; ++i) {
        struct nwaios_tensor *t = &mctx->inputs[i];
        if (t->name[0] == '\0' || t->size == 0 || t->buffer == NULL) {
            continue;
        }
        const uint32_t expected = STC_INPUT_LEN * sizeof(float);
        if (t->size < expected) {
            LOG_ERROR("input tensor '%s' too small: %u < %u",
                      t->name, t->size, expected);
            return -1;
        }
        float *buf = (float *)t->buffer;
        for (uint32_t j = 0; j < STC_INPUT_LEN; ++j) {
            uint8_t byte = (uint8_t)((g_packet_seq * 131u + j * 17u + 7u) & 0xFFu);
            buf[j] = (float)byte / 255.0f;
        }
        ++g_packet_seq;
        return 0;
    }
    LOG_ERROR("no input tensor available on model context");
    return -1;
}

/* Numerically stable softmax of N floats in-place. */
static void softmax(float *v, uint32_t n)
{
    float max = v[0];
    for (uint32_t i = 1; i < n; ++i) {
        if (v[i] > max) max = v[i];
    }
    float sum = 0.0f;
    for (uint32_t i = 0; i < n; ++i) {
        v[i] = expf(v[i] - max);
        sum += v[i];
    }
    if (sum <= 0.0f) sum = 1.0f;
    for (uint32_t i = 0; i < n; ++i) {
        v[i] /= sum;
    }
}

/*
 * Decode logits -> top class + confidence.
 *
 * Reads STC_NUM_CLASSES floats from the first non-empty output tensor,
 * runs softmax, picks argmax, and packs the result into decision_t for
 * turnkey_act() (which logs to syslog).
 */
int consume_outputs(struct nwaios_model_ctx *mctx, decision_t *out_decision)
{
    if (mctx == NULL || out_decision == NULL) {
        return -1;
    }
    out_decision->valid = 0;
    out_decision->score = 0.0f;
    out_decision->label = -1;

    for (uint8_t i = 0; i < NWAIOS_TENSOR_MAX; ++i) {
        struct nwaios_tensor *t = &mctx->outputs[i];
        if (t->name[0] == '\0' || t->size == 0 || t->buffer == NULL) {
            continue;
        }
        const uint32_t expected = STC_NUM_CLASSES * sizeof(float);
        if (t->size < expected) {
            LOG_ERROR("output tensor '%s' too small: %u < %u",
                      t->name, t->size, expected);
            return -1;
        }

        float probs[STC_NUM_CLASSES];
        memcpy(probs, t->buffer, expected);
        softmax(probs, STC_NUM_CLASSES);

        uint32_t argmax = 0;
        for (uint32_t k = 1; k < STC_NUM_CLASSES; ++k) {
            if (probs[k] > probs[argmax]) argmax = k;
        }
        out_decision->label = (int32_t)argmax;
        out_decision->score = probs[argmax];
        out_decision->valid = 1;

        LOG_TRACE("logits[%s] -> class=%s p=%.3f",
                  t->name, STC_CLASS_NAMES[argmax], (double)probs[argmax]);
        return 0;
    }
    LOG_ERROR("no output tensor available on model context");
    return -1;
}

/* Expose class name lookup so turnkey_act can render syslog lines. */
const char *stc_class_name(int32_t label)
{
    if (label < 0 || (uint32_t)label >= STC_NUM_CLASSES) {
        return "unknown";
    }
    return STC_CLASS_NAMES[label];
}
