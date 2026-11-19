/*
 * stc_classifier — debugging / logging utilities
 *
 * Mirrors the pattern from the production fault-detection reference:
 * a log_message() macro keyed on log levels, gated by an
 * environment variable so production builds can stay quiet.
 *
 * Replace this scaffold's implementation with a call into
 * gwapps_utils_lib's gwapps_dbg.h (when linked) for unified
 * logging across gwapps apps.
 */

#ifndef DEBUGGING_H
#define DEBUGGING_H

#include <stdarg.h>

/* Log levels — increasing verbosity. Set DEBUG_LEVEL env var to one
 * of the integer values to gate output. */
typedef enum {
    LOG_LEVEL_ERROR = 0,
    LOG_LEVEL_WARN  = 1,
    LOG_LEVEL_INFO  = 2,
    LOG_LEVEL_DEBUG = 3,
    LOG_LEVEL_TRACE = 4,
} log_level_t;

/* Initialize from env (DEBUG_LEVEL=N). Idempotent. */
void log_init(void);

/* The actual logger — printf-style. Honors the level set by log_init. */
void log_message(log_level_t level, const char *fmt, ...);

/* Convenience wrappers. */
#define LOG_ERROR(...)  log_message(LOG_LEVEL_ERROR, __VA_ARGS__)
#define LOG_WARN(...)   log_message(LOG_LEVEL_WARN,  __VA_ARGS__)
#define LOG_INFO(...)   log_message(LOG_LEVEL_INFO,  __VA_ARGS__)
#define LOG_DEBUG(...)  log_message(LOG_LEVEL_DEBUG, __VA_ARGS__)
#define LOG_TRACE(...)  log_message(LOG_LEVEL_TRACE, __VA_ARGS__)

#endif /* DEBUGGING_H */
