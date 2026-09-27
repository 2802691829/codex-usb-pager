#ifndef CODEX_PAGER_CORE_H
#define CODEX_PAGER_CORE_H

#include <stdbool.h>
#include <stdint.h>

#define PAGER_BALANCE_CAPACITY 13U
#define PAGER_OFFLINE_TIMEOUT_MS 8000U

typedef enum {
    PAGER_IDLE = 0,
    PAGER_RUNNING,
    PAGER_MULTI,
    PAGER_WAIT,
    PAGER_DONE,
    PAGER_ERROR,
    PAGER_OFFLINE
} pager_state_t;

typedef enum {
    PAGER_EVENT_NONE = 0,
    PAGER_EVENT_WAIT,
    PAGER_EVENT_DONE,
    PAGER_EVENT_ERROR
} pager_event_t;

typedef struct {
    pager_state_t state;
    uint32_t running;
    uint32_t waiting;
    uint32_t done;
    char balance[PAGER_BALANCE_CAPACITY];
    pager_event_t event;
} pager_snapshot_t;

bool pager_parse_line(const char *line, pager_snapshot_t *snapshot);
pager_state_t pager_select_state(const pager_snapshot_t *snapshot);
pager_state_t pager_apply_timeout(
    pager_state_t state, uint32_t last_valid_ms, uint32_t now_ms);

#endif
