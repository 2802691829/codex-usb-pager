#ifndef CODEX_ST7789_PROFILE_H
#define CODEX_ST7789_PROFILE_H

#include <stddef.h>
#include <stdint.h>

#define ST7789_INIT_DATA_CAPACITY 14U

typedef struct {
    uint8_t command;
    uint8_t length;
    uint8_t data[ST7789_INIT_DATA_CAPACITY];
} st7789_init_step_t;

extern const st7789_init_step_t g_st7789_vendor_init[];
extern const size_t g_st7789_vendor_init_count;

#endif
