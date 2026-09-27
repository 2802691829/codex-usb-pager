#include "display_pattern.h"

#include "board_config.h"

uint16_t pager_rgb565(uint8_t red, uint8_t green, uint8_t blue) {
    return (uint16_t)(((uint16_t)(red & 0xF8U) << 8U) |
                      ((uint16_t)(green & 0xFCU) << 3U) |
                      ((uint16_t)blue >> 3U));
}

uint16_t pager_display_test_color(uint16_t x, uint16_t y) {
    const uint16_t half_width = PAGER_DISPLAY_WIDTH / 2U;
    const uint16_t half_height = PAGER_DISPLAY_HEIGHT / 2U;

    if (x < 5U || y < 5U || x >= PAGER_DISPLAY_WIDTH - 5U ||
        y >= PAGER_DISPLAY_HEIGHT - 5U) {
        return pager_rgb565(0U, 0U, 0U);
    }
    if (x < 28U && y < 28U) {
        return pager_rgb565(255U, 220U, 0U);
    }
    if (x >= PAGER_DISPLAY_WIDTH - 28U && y < 28U) {
        return pager_rgb565(0U, 220U, 255U);
    }
    if (x < half_width && y < half_height) {
        return pager_rgb565(255U, 0U, 0U);
    }
    if (x >= half_width && y < half_height) {
        return pager_rgb565(0U, 255U, 0U);
    }
    if (x < half_width) {
        return pager_rgb565(0U, 0U, 255U);
    }
    return pager_rgb565(255U, 255U, 255U);
}
