#include "led_effects.h"

pager_rgb_t pager_led_sample(pager_state_t state, uint32_t elapsed_ms) {
    const pager_rgb_t running = {PAGER_LED_CHANNEL_MAX, 0U, 0U};
    const pager_rgb_t stopped = {8U, 8U, 8U};

    (void)elapsed_ms;
    return state == PAGER_RUNNING || state == PAGER_MULTI ? running : stopped;
}

uint32_t pager_led_pack_rgb(pager_rgb_t color) {
    return ((uint32_t)color.g << 24U) |
           ((uint32_t)color.r << 16U) |
           ((uint32_t)color.b << 8U);
}
