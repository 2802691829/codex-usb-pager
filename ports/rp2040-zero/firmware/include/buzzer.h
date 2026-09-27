#ifndef CODEX_BUZZER_H
#define CODEX_BUZZER_H

#include "pager_core.h"

#include <stdbool.h>
#include <stdint.h>

#define PAGER_BUZZER_ON_MS 25U
#define PAGER_BUZZER_GAP_MS 180U

typedef struct {
    uint8_t remaining;
    bool active;
    uint32_t changed_ms;
} pager_buzzer_t;

uint8_t pager_buzzer_event_pulses(pager_event_t event);
void pager_buzzer_init(pager_buzzer_t *buzzer, uint32_t now_ms);
void pager_buzzer_start(
    pager_buzzer_t *buzzer, uint8_t pulses, uint32_t now_ms);
bool pager_buzzer_update(pager_buzzer_t *buzzer, uint32_t now_ms);
bool pager_buzzer_is_active(const pager_buzzer_t *buzzer);

#endif
