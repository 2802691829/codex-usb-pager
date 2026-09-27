#include "pager_core.h"

#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

#define PAGER_LINE_CAPACITY 96U
#define PAGER_TOKEN_COUNT 7U

static char *next_token(char **cursor) {
    char *start;

    while (**cursor == ' ' || **cursor == '\t') {
        ++*cursor;
    }
    if (**cursor == '\0') {
        return NULL;
    }

    start = *cursor;
    while (**cursor != '\0' && **cursor != ' ' && **cursor != '\t') {
        ++*cursor;
    }
    if (**cursor != '\0') {
        **cursor = '\0';
        ++*cursor;
    }
    return start;
}

static bool parse_state(const char *token, pager_state_t *state) {
    if (strcmp(token, "IDLE") == 0) {
        *state = PAGER_IDLE;
    } else if (strcmp(token, "RUNNING") == 0) {
        *state = PAGER_RUNNING;
    } else if (strcmp(token, "WAIT") == 0) {
        *state = PAGER_WAIT;
    } else if (strcmp(token, "DONE") == 0) {
        *state = PAGER_DONE;
    } else if (strcmp(token, "ERROR") == 0) {
        *state = PAGER_ERROR;
    } else {
        return false;
    }
    return true;
}

static bool parse_event(const char *token, pager_event_t *event) {
    if (strcmp(token, "NONE") == 0) {
        *event = PAGER_EVENT_NONE;
    } else if (strcmp(token, "WAIT") == 0) {
        *event = PAGER_EVENT_WAIT;
    } else if (strcmp(token, "DONE") == 0) {
        *event = PAGER_EVENT_DONE;
    } else if (strcmp(token, "ERROR") == 0) {
        *event = PAGER_EVENT_ERROR;
    } else {
        return false;
    }
    return true;
}

static bool parse_count(const char *token, const char *prefix, uint32_t *value) {
    const size_t prefix_length = strlen(prefix);
    const char *number;
    char *end;
    unsigned long parsed;

    if (strncmp(token, prefix, prefix_length) != 0) {
        return false;
    }
    number = token + prefix_length;
    if (*number == '\0' || !isdigit((unsigned char)*number)) {
        return false;
    }
    for (end = (char *)number; *end != '\0'; ++end) {
        if (!isdigit((unsigned char)*end)) {
            return false;
        }
    }

    errno = 0;
    parsed = strtoul(number, &end, 10);
    if (errno == ERANGE || *end != '\0' || parsed > UINT32_MAX) {
        return false;
    }
    *value = (uint32_t)parsed;
    return true;
}

static bool parse_balance(const char *token, char *balance) {
    static const char prefix[] = "BAL=";
    const char *value;
    size_t length;
    size_t index;

    if (strncmp(token, prefix, sizeof(prefix) - 1U) != 0) {
        return false;
    }
    value = token + sizeof(prefix) - 1U;
    length = strlen(value);
    if (length == 0U || length >= PAGER_BALANCE_CAPACITY) {
        return false;
    }
    for (index = 0U; index < length; ++index) {
        const unsigned char ch = (unsigned char)value[index];
        if (!isalnum(ch) && ch != '.' && ch != '%' && ch != '-' && ch != '_') {
            return false;
        }
    }
    memcpy(balance, value, length + 1U);
    return true;
}

bool pager_parse_line(const char *line, pager_snapshot_t *snapshot) {
    pager_snapshot_t parsed = {0};
    char buffer[PAGER_LINE_CAPACITY];
    char *tokens[PAGER_TOKEN_COUNT];
    char *cursor;
    const size_t length = line == NULL ? 0U : strlen(line);
    size_t index;

    if (line == NULL || snapshot == NULL || length == 0U ||
        length >= sizeof(buffer)) {
        return false;
    }
    memcpy(buffer, line, length + 1U);
    cursor = buffer;

    for (index = 0U; index < PAGER_TOKEN_COUNT; ++index) {
        tokens[index] = next_token(&cursor);
        if (tokens[index] == NULL) {
            return false;
        }
    }
    if (next_token(&cursor) != NULL || strcmp(tokens[0], "STATE") != 0) {
        return false;
    }
    if (!parse_state(tokens[1], &parsed.state) ||
        !parse_count(tokens[2], "RUN=", &parsed.running) ||
        !parse_count(tokens[3], "WAIT=", &parsed.waiting) ||
        !parse_count(tokens[4], "DONE=", &parsed.done) ||
        !parse_balance(tokens[5], parsed.balance)) {
        return false;
    }
    if (strncmp(tokens[6], "EV=", 3U) != 0 ||
        !parse_event(tokens[6] + 3U, &parsed.event)) {
        return false;
    }

    *snapshot = parsed;
    return true;
}

pager_state_t pager_select_state(const pager_snapshot_t *snapshot) {
    if (snapshot == NULL) {
        return PAGER_OFFLINE;
    }
    if (snapshot->state == PAGER_ERROR || snapshot->event == PAGER_EVENT_ERROR) {
        return PAGER_ERROR;
    }
    if (snapshot->state == PAGER_WAIT || snapshot->waiting > 0U ||
        snapshot->event == PAGER_EVENT_WAIT) {
        return PAGER_WAIT;
    }
    if (snapshot->running > 1U) {
        return PAGER_MULTI;
    }
    if (snapshot->state == PAGER_RUNNING || snapshot->running == 1U) {
        return PAGER_RUNNING;
    }
    if (snapshot->state == PAGER_DONE || snapshot->event == PAGER_EVENT_DONE) {
        return PAGER_DONE;
    }
    return PAGER_IDLE;
}

pager_state_t pager_apply_timeout(
    pager_state_t state, uint32_t last_valid_ms, uint32_t now_ms) {
    if ((uint32_t)(now_ms - last_valid_ms) >= PAGER_OFFLINE_TIMEOUT_MS) {
        return PAGER_OFFLINE;
    }
    return state;
}
