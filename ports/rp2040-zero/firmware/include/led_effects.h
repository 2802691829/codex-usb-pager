#ifndef CODEX_LED_EFFECTS_H
#define CODEX_LED_EFFECTS_H

#include "pager_core.h"

#include <stdint.h>

#define PAGER_LED_CHANNEL_MAX 20U

typedef struct {
    uint8_t r;
    uint8_t g;
    uint8_t b;
} pager_rgb_t;

pager_rgb_t pager_led_sample(pager_state_t state, uint32_t elapsed_ms);
uint32_t pager_led_pack_rgb(pager_rgb_t color);

#endif
