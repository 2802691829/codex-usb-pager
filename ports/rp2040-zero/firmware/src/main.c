#include "board_config.h"
#include "buzzer.h"
#include "display_ui.h"
#include "led_effects.h"
#include "pager_core.h"
#include "pager_stream.h"
#include "st7789.h"

#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "pico/stdlib.h"
#include "ws2812.pio.h"

#include <stdbool.h>
#include <stdint.h>

_Static_assert(PAGER_WS2812_PIN == 16U, "RP2040-Zero WS2812 pin mismatch");

typedef struct {
    PIO pio;
    uint sm;
} ws2812_output_t;

static uint32_t now_ms(void) {
    return to_ms_since_boot(get_absolute_time());
}

static ws2812_output_t ws2812_init(void) {
    ws2812_output_t output;
    const uint offset = pio_add_program(pio0, &ws2812_program);

    output.pio = pio0;
    output.sm = pio_claim_unused_sm(output.pio, true);
    ws2812_program_init(
        output.pio, output.sm, offset, PAGER_WS2812_PIN, 800000.0f, false);
    return output;
}

static void ws2812_try_write(ws2812_output_t output, pager_rgb_t color) {
    if (!pio_sm_is_tx_fifo_full(output.pio, output.sm)) {
        pio_sm_put(output.pio, output.sm, pager_led_pack_rgb(color));
    }
}

static int read_usb_byte(void *context) {
    const int byte = getchar_timeout_us(0U);
    (void)context;
    return byte == PICO_ERROR_TIMEOUT ? PAGER_STREAM_NO_BYTE : byte;
}

int main(void) {
    pager_stream_t stream = {{0}, 0U};
    pager_snapshot_t snapshot = {0};
    pager_state_t state = PAGER_OFFLINE;
    uint32_t last_valid_snapshot_ms = now_ms();
    uint32_t state_started_ms = last_valid_snapshot_ms;
    uint32_t last_led_update_ms = last_valid_snapshot_ms;
    pager_buzzer_t buzzer;
    pager_event_t last_buzzer_event = PAGER_EVENT_NONE;
    ws2812_output_t ws2812;

    stdio_init_all();
    gpio_init(PAGER_BUZZER_PIN);
    gpio_set_dir(PAGER_BUZZER_PIN, GPIO_OUT);
    gpio_put(PAGER_BUZZER_PIN, true);
    pager_buzzer_init(&buzzer, last_valid_snapshot_ms);
    pager_buzzer_start(&buzzer, 1U, last_valid_snapshot_ms);
    gpio_put(PAGER_BUZZER_PIN, !pager_buzzer_is_active(&buzzer));
    ws2812 = ws2812_init();
    st7789_init();
    st7789_set_backlight(true);
    pager_display_ui_init(state, now_ms());

    while (true) {
        const uint32_t current_ms = now_ms();
        if (pager_stream_drain(
                &stream, read_usb_byte, NULL, &snapshot) > 0U) {
            const pager_state_t selected = pager_select_state(&snapshot);
            last_valid_snapshot_ms = current_ms;
            if (selected != state) {
                state = selected;
                state_started_ms = current_ms;
            }
            pager_display_ui_set_snapshot(
                state, snapshot.running, snapshot.balance, current_ms);
            if (snapshot.event == PAGER_EVENT_NONE) {
                last_buzzer_event = PAGER_EVENT_NONE;
            } else if (snapshot.event != last_buzzer_event) {
                pager_buzzer_start(
                    &buzzer,
                    pager_buzzer_event_pulses(snapshot.event),
                    current_ms);
                gpio_put(PAGER_BUZZER_PIN, !pager_buzzer_is_active(&buzzer));
                last_buzzer_event = snapshot.event;
            }
        }
        if (pager_buzzer_update(&buzzer, current_ms)) {
            gpio_put(PAGER_BUZZER_PIN, !pager_buzzer_is_active(&buzzer));
        }

        {
            const pager_state_t timed_state = pager_apply_timeout(
                state, last_valid_snapshot_ms, current_ms);
            if (timed_state != state) {
                state = timed_state;
                state_started_ms = current_ms;
                pager_display_ui_set_state(state, current_ms);
            }
        }

        if ((uint32_t)(current_ms - last_led_update_ms) >= PAGER_LED_UPDATE_MS) {
            const pager_rgb_t color = pager_led_sample(
                state, (uint32_t)(current_ms - state_started_ms));
            ws2812_try_write(ws2812, color);
            last_led_update_ms = current_ms;
        }
        pager_display_ui_update(current_ms);
        sleep_ms(1U);
    }
}
