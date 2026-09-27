#include "st7789.h"

#include "board_config.h"
#include "display_pattern.h"
#include "st7789_profile.h"

#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "pico/stdlib.h"
#include "st7789_spi.pio.h"

#include <stddef.h>
#include <stdint.h>

_Static_assert(PAGER_DISPLAY_RES_PIN == 10U, "Display reset must use GP10");
_Static_assert(PAGER_DISPLAY_SDA_PIN == 11U, "Display data must use GP11");
_Static_assert(PAGER_DISPLAY_SCL_PIN == 12U, "Display clock must use GP12");

static PIO display_pio = pio0;
static uint display_sm;
static int display_dma_channel;
static dma_channel_config display_dma_config;
static uint32_t display_word_buffer[PAGER_DISPLAY_WIDTH * 2U];

static void wait_for_bus(void) {
    while (!pio_sm_is_tx_fifo_empty(display_pio, display_sm)) {
        tight_loop_contents();
    }
    sleep_us(2U);
}

void st7789_wait_idle(void) {
    wait_for_bus();
}

static void write_bytes(const uint8_t *data, size_t length) {
    size_t index;
    for (index = 0U; index < length; ++index) {
        pio_sm_put_blocking(
            display_pio, display_sm, (uint32_t)data[index] << 24U);
    }
}

static void write_words_dma(const uint32_t *words, size_t count) {
    dma_channel_configure(
        display_dma_channel,
        &display_dma_config,
        &display_pio->txf[display_sm],
        words,
        count,
        true);
    dma_channel_wait_for_finish_blocking(display_dma_channel);
}

static void write_command(uint8_t command) {
    wait_for_bus();
    gpio_put(PAGER_DISPLAY_DC_PIN, false);
    write_bytes(&command, 1U);
}

static void write_data(const uint8_t *data, size_t length) {
    wait_for_bus();
    gpio_put(PAGER_DISPLAY_DC_PIN, true);
    write_bytes(data, length);
}

static void set_window(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1) {
    uint8_t bounds[4];

    write_command(0x2AU);
    bounds[0] = (uint8_t)(x0 >> 8U);
    bounds[1] = (uint8_t)x0;
    bounds[2] = (uint8_t)(x1 >> 8U);
    bounds[3] = (uint8_t)x1;
    write_data(bounds, sizeof(bounds));

    write_command(0x2BU);
    bounds[0] = (uint8_t)(y0 >> 8U);
    bounds[1] = (uint8_t)y0;
    bounds[2] = (uint8_t)(y1 >> 8U);
    bounds[3] = (uint8_t)y1;
    write_data(bounds, sizeof(bounds));
    write_command(0x2CU);
}

void st7789_begin_pixels(
    uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1) {
    set_window(x0, y0, x1, y1);
    wait_for_bus();
    gpio_put(PAGER_DISPLAY_DC_PIN, true);
}

void st7789_write_pixels(const uint16_t *pixels, size_t count) {
    size_t index;

    if (pixels == NULL || count == 0U || count > PAGER_DISPLAY_WIDTH) {
        return;
    }
    for (index = 0U; index < count; ++index) {
        display_word_buffer[index * 2U] =
            (uint32_t)(pixels[index] >> 8U) << 24U;
        display_word_buffer[index * 2U + 1U] =
            (uint32_t)(uint8_t)pixels[index] << 24U;
    }
    write_words_dma(display_word_buffer, count * 2U);
}

void st7789_fill(uint16_t color) {
    uint16_t row[PAGER_DISPLAY_WIDTH];
    uint16_t x;
    uint16_t y;

    for (x = 0U; x < PAGER_DISPLAY_WIDTH; ++x) {
        row[x] = color;
    }
    st7789_begin_pixels(
        0U, 0U, PAGER_DISPLAY_WIDTH - 1U, PAGER_DISPLAY_HEIGHT - 1U);
    for (y = 0U; y < PAGER_DISPLAY_HEIGHT; ++y) {
        st7789_write_pixels(row, PAGER_DISPLAY_WIDTH);
    }
    st7789_wait_idle();
}

void st7789_set_backlight(bool enabled) {
    gpio_put(PAGER_DISPLAY_BLK_PIN, enabled);
}

void st7789_init(void) {
    size_t index;

    gpio_init(PAGER_DISPLAY_DC_PIN);
    gpio_init(PAGER_DISPLAY_RES_PIN);
    gpio_init(PAGER_DISPLAY_BLK_PIN);
    gpio_set_dir(PAGER_DISPLAY_DC_PIN, GPIO_OUT);
    gpio_set_dir(PAGER_DISPLAY_RES_PIN, GPIO_OUT);
    gpio_set_dir(PAGER_DISPLAY_BLK_PIN, GPIO_OUT);
    st7789_set_backlight(false);

    {
        const uint offset = pio_add_program(display_pio, &st7789_spi_program);
        display_sm = pio_claim_unused_sm(display_pio, true);
        st7789_spi_program_init(
            display_pio,
            display_sm,
            offset,
            PAGER_DISPLAY_SDA_PIN,
            PAGER_DISPLAY_SCL_PIN,
            (float)PAGER_DISPLAY_SPI_HZ);
    }
    display_dma_channel = dma_claim_unused_channel(true);
    display_dma_config = dma_channel_get_default_config(display_dma_channel);
    channel_config_set_transfer_data_size(&display_dma_config, DMA_SIZE_32);
    channel_config_set_read_increment(&display_dma_config, true);
    channel_config_set_write_increment(&display_dma_config, false);
    channel_config_set_dreq(
        &display_dma_config, pio_get_dreq(display_pio, display_sm, true));

    gpio_put(PAGER_DISPLAY_RES_PIN, false);
    sleep_ms(20U);
    gpio_put(PAGER_DISPLAY_RES_PIN, true);
    sleep_ms(20U);

    for (index = 0U; index < g_st7789_vendor_init_count; ++index) {
        const st7789_init_step_t *step = &g_st7789_vendor_init[index];
        write_command(step->command);
        if (step->length > 0U) {
            write_data(step->data, step->length);
        }
        if (step->command == 0x11U) {
            sleep_ms(120U);
        } else if (step->command == 0x29U) {
            sleep_ms(20U);
        }
    }
}

void st7789_show_test_pattern(void) {
    uint32_t scanline[PAGER_DISPLAY_WIDTH * 2U];
    uint16_t y;

    set_window(
        0U, 0U, PAGER_DISPLAY_WIDTH - 1U, PAGER_DISPLAY_HEIGHT - 1U);
    gpio_put(PAGER_DISPLAY_DC_PIN, true);
    for (y = 0U; y < PAGER_DISPLAY_HEIGHT; ++y) {
        uint16_t x;
        for (x = 0U; x < PAGER_DISPLAY_WIDTH; ++x) {
            const uint16_t color = pager_display_test_color(x, y);
            scanline[x * 2U] = (uint32_t)(color >> 8U) << 24U;
            scanline[x * 2U + 1U] = (uint32_t)(uint8_t)color << 24U;
        }
        write_words_dma(scanline, PAGER_DISPLAY_WIDTH * 2U);
    }
    wait_for_bus();
}
