/*
 * stc_classifier — debugging / logging implementation
 *
 * Reads DEBUG_LEVEL once on first log_init() call (or on first
 * log_message() if init was skipped). Defaults to INFO. Output goes
 * to stderr so LCM's journalctl integration captures it.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "debugging.h"

#define APP_NAME "stc_classifier"

static log_level_t g_level = LOG_LEVEL_INFO;
static int         g_initialized = 0;

void log_init(void)
{
    if (g_initialized) {
        return;
    }
    const char *env = getenv("DEBUG_LEVEL");
    if (env != NULL) {
        int v = atoi(env);
        if (v >= LOG_LEVEL_ERROR && v <= LOG_LEVEL_TRACE) {
            g_level = (log_level_t)v;
        }
    }
    g_initialized = 1;
}

static const char *level_label(log_level_t level)
{
    switch (level) {
        case LOG_LEVEL_ERROR: return "ERROR";
        case LOG_LEVEL_WARN:  return "WARN";
        case LOG_LEVEL_INFO:  return "INFO";
        case LOG_LEVEL_DEBUG: return "DEBUG";
        case LOG_LEVEL_TRACE: return "TRACE";
        default:              return "?";
    }
}

void log_message(log_level_t level, const char *fmt, ...)
{
    if (!g_initialized) {
        log_init();
    }
    if (level > g_level) {
        return;
    }
    /* Timestamp + level + app prefix. Production reference uses a
     * compact format; tweak as needed. */
    time_t now = time(NULL);
    struct tm tm_buf;
    char ts[24];
    if (localtime_r(&now, &tm_buf) != NULL &&
        strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S", &tm_buf) > 0) {
        fprintf(stderr, "[%s %s %s] ", ts, level_label(level), APP_NAME);
    } else {
        fprintf(stderr, "[%s %s] ", level_label(level), APP_NAME);
    }
    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    /* Add newline if the caller didn't. */
    size_t n = strlen(fmt);
    if (n == 0 || fmt[n - 1] != '\n') {
        fputc('\n', stderr);
    }
}
