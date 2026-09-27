#ifndef CODEX_ST7789_H
#define CODEX_ST7789_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

void st7789_init(void);
void st7789_show_test_pattern(void);
void st7789_set_backlight(bool enabled);
void st7789_begin_pixels(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1);
void st7789_write_pixels(const uint16_t *pixels, size_t count);
void st7789_fill(uint16_t color);
void st7789_wait_idle(void);

#endif
