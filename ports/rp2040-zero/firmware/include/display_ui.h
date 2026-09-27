#ifndef CODEX_DISPLAY_UI_H
#define CODEX_DISPLAY_UI_H

#include "pager_core.h"

#include <stdint.h>

void pager_display_ui_init(pager_state_t state, uint32_t now_ms);
void pager_display_ui_set_state(pager_state_t state, uint32_t now_ms);
void pager_display_ui_set_snapshot(
    pager_state_t state,
    uint32_t running_count,
    const char *balance,
    uint32_t now_ms);
void pager_display_ui_update(uint32_t now_ms);

#endif
