#include "buzzer.h"

#include <stddef.h>

uint8_t pager_buzzer_event_pulses(pager_event_t event) {
    switch (event) {
        case PAGER_EVENT_WAIT:
            return 3U;
        case PAGER_EVENT_DONE:
            return 1U;
        case PAGER_EVENT_ERROR:
            return 5U;
        default:
            return 0U;
    }
}

void pager_buzzer_init(pager_buzzer_t *buzzer, uint32_t now_ms) {
    if (buzzer == NULL) {
        return;
    }
    buzzer->remaining = 0U;
    buzzer->active = false;
    buzzer->changed_ms = now_ms;
}

void pager_buzzer_start(
    pager_buzzer_t *buzzer, uint8_t pulses, uint32_t now_ms) {
    if (buzzer == NULL) {
        return;
    }
    buzzer->remaining = pulses;
    buzzer->active = pulses != 0U;
    buzzer->changed_ms = now_ms;
}

bool pager_buzzer_update(pager_buzzer_t *buzzer, uint32_t now_ms) {
    uint32_t duration;

    if (buzzer == NULL || buzzer->remaining == 0U) {
        return false;
    }
    duration = buzzer->active ? PAGER_BUZZER_ON_MS : PAGER_BUZZER_GAP_MS;
    if ((uint32_t)(now_ms - buzzer->changed_ms) < duration) {
        return false;
    }
    buzzer->changed_ms = now_ms;
    if (buzzer->active) {
        --buzzer->remaining;
        buzzer->active = false;
    } else if (buzzer->remaining != 0U) {
        buzzer->active = true;
    }
    return true;
}

bool pager_buzzer_is_active(const pager_buzzer_t *buzzer) {
    return buzzer != NULL && buzzer->active;
}
