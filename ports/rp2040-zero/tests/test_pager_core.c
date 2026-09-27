#include "pager_core.h"
#include "pager_stream.h"
#include "blossom_motion.h"
#include "buzzer.h"
#include "led_effects.h"
#include "display_pattern.h"
#include "display_scene.h"
#include "st7789.h"
#include "st7789_profile.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
static void test_assert_fail(
    const char *condition,
    const char *file,
    int line) {
    fprintf(
        stderr,
        "ASSERT FAILED: %s (%s:%d)\n",
        condition,
        file,
        line);
    fflush(stderr);
    exit(EXIT_FAILURE);
}

#undef assert
#define assert(condition) \
    ((condition) ? (void)0 : test_assert_fail(#condition, __FILE__, __LINE__))
#endif

static void test_valid_multi_snapshot(void) {
    pager_snapshot_t snapshot;

    assert(pager_parse_line(
        "STATE RUNNING RUN=3 WAIT=0 DONE=14 BAL=82 EV=NONE", &snapshot));
    assert(snapshot.state == PAGER_RUNNING);
    assert(snapshot.running == 3U);
    assert(snapshot.waiting == 0U);
    assert(snapshot.done == 14U);
    assert(strcmp(snapshot.balance, "82") == 0);
    assert(snapshot.event == PAGER_EVENT_NONE);
    assert(pager_select_state(&snapshot) == PAGER_MULTI);
}

static void test_display_ghost_count_caps_additional_tasks(void) {
    assert(pager_scene_ghost_count(PAGER_RUNNING, 1U) == 0U);
    assert(pager_scene_ghost_count(PAGER_MULTI, 2U) == 1U);
    assert(pager_scene_ghost_count(PAGER_MULTI, 3U) == 2U);
    assert(pager_scene_ghost_count(PAGER_MULTI, 4U) == 3U);
    assert(pager_scene_ghost_count(PAGER_MULTI, 99U) == 3U);
    assert(pager_scene_ghost_count(PAGER_WAIT, 3U) == 0U);
}

static void test_ghost_count_transition_fades_only_changed_layers(void) {
    uint8_t opacity[3];

    pager_scene_ghost_opacity(1U, 3U, 0U, opacity);
    assert(opacity[0] == 255U);
    assert(opacity[1] == 0U);
    assert(opacity[2] == 0U);

    pager_scene_ghost_opacity(1U, 3U, 160U, opacity);
    assert(opacity[0] == 255U);
    assert(opacity[1] > 0U && opacity[1] < 255U);
    assert(opacity[2] > 0U && opacity[2] < 255U);

    pager_scene_ghost_opacity(1U, 3U, 320U, opacity);
    assert(opacity[0] == 255U);
    assert(opacity[1] == 255U);
    assert(opacity[2] == 255U);
}

static void test_buzzer_event_pulse_counts_and_nonblocking_timing(void) {
    pager_buzzer_t buzzer;

    assert(pager_buzzer_event_pulses(PAGER_EVENT_NONE) == 0U);
    assert(pager_buzzer_event_pulses(PAGER_EVENT_WAIT) == 3U);
    assert(pager_buzzer_event_pulses(PAGER_EVENT_DONE) == 1U);
    assert(pager_buzzer_event_pulses(PAGER_EVENT_ERROR) == 5U);

    pager_buzzer_init(&buzzer, 0U);
    pager_buzzer_start(&buzzer, 3U, 0U);
    assert(pager_buzzer_is_active(&buzzer));
    assert(!pager_buzzer_update(&buzzer, 24U));
    assert(pager_buzzer_update(&buzzer, 25U));
    assert(!pager_buzzer_is_active(&buzzer));
    assert(!pager_buzzer_update(&buzzer, 204U));
    assert(pager_buzzer_update(&buzzer, 205U));
    assert(pager_buzzer_is_active(&buzzer));
}

static void test_wait_priority_and_timeout(void) {
    pager_snapshot_t snapshot;

    assert(pager_parse_line(
        "STATE RUNNING RUN=2 WAIT=1 DONE=4 BAL=NA EV=WAIT", &snapshot));
    assert(pager_select_state(&snapshot) == PAGER_WAIT);
    assert(pager_apply_timeout(PAGER_WAIT, 1000U, 8999U) == PAGER_WAIT);
    assert(pager_apply_timeout(PAGER_WAIT, 1000U, 9000U) == PAGER_OFFLINE);
}

static void test_event_and_state_priority(void) {
    pager_snapshot_t snapshot;

    assert(pager_parse_line(
        "STATE IDLE RUN=2 WAIT=1 DONE=9 BAL=74% EV=ERROR", &snapshot));
    assert(pager_select_state(&snapshot) == PAGER_ERROR);

    assert(pager_parse_line(
        "STATE IDLE RUN=2 WAIT=1 DONE=9 BAL=74% EV=NONE", &snapshot));
    assert(pager_select_state(&snapshot) == PAGER_WAIT);
}

static void test_done_and_idle_selection(void) {
    pager_snapshot_t snapshot;

    assert(pager_parse_line(
        "STATE DONE RUN=0 WAIT=0 DONE=1 BAL=NA EV=DONE", &snapshot));
    assert(pager_select_state(&snapshot) == PAGER_DONE);

    assert(pager_parse_line(
        "STATE IDLE RUN=0 WAIT=0 DONE=1 BAL=NA EV=NONE", &snapshot));
    assert(pager_select_state(&snapshot) == PAGER_IDLE);
}

static void test_balance_parser_boundaries(void) {
    pager_snapshot_t snapshot;

    assert(pager_parse_line(
        "STATE IDLE RUN=0 WAIT=0 DONE=0 BAL=0 EV=NONE", &snapshot));
    assert(strcmp(snapshot.balance, "0") == 0);
    assert(pager_parse_line(
        "STATE IDLE RUN=0 WAIT=0 DONE=0 BAL=100 EV=NONE", &snapshot));
    assert(strcmp(snapshot.balance, "100") == 0);
}

static void test_invalid_lines_are_rejected(void) {
    static const char *const invalid_lines[] = {
        "STATE RUNNING RUN=x WAIT=0 DONE=0 BAL=NA EV=NONE",
        "STATE UNKNOWN RUN=0 WAIT=0 DONE=0 BAL=NA EV=NONE",
        "STATE IDLE RUN=0 WAIT=0 DONE=0 BAL=NA EV=LOUD",
        "STATE IDLE RUN=-1 WAIT=0 DONE=0 BAL=NA EV=NONE",
        "STATE IDLE RUN=0 WAIT=0 DONE=0 BAL=ABCDEFGHIJKLM EV=NONE",
        "STATE IDLE RUN=0 WAIT=0 DONE=0 EV=NONE",
        "STATE IDLE RUN=0 WAIT=0 DONE=0 BAL=NA EV=NONE EXTRA=1",
        "STATE IDLE RUN=0 WAIT=0 DONE=0 BAL=NA",
        "IDLE RUN=0 WAIT=0 DONE=0 BAL=NA EV=NONE",
        "",
    };
    pager_snapshot_t snapshot;
    size_t index;

    assert(!pager_parse_line(NULL, &snapshot));
    assert(!pager_parse_line(invalid_lines[0], NULL));

    for (index = 0U; index < sizeof(invalid_lines) / sizeof(invalid_lines[0]); ++index) {
        assert(!pager_parse_line(invalid_lines[index], &snapshot));
    }
}

static void test_timeout_handles_millisecond_wraparound(void) {
    assert(pager_apply_timeout(PAGER_RUNNING, UINT32_MAX - 3999U, 3999U) ==
           PAGER_RUNNING);
    assert(pager_apply_timeout(PAGER_RUNNING, UINT32_MAX - 3999U, 4000U) ==
           PAGER_OFFLINE);
}

static void assert_bounded(pager_rgb_t rgb) {
    assert(rgb.r <= PAGER_LED_CHANNEL_MAX);
    assert(rgb.g <= PAGER_LED_CHANNEL_MAX);
    assert(rgb.b <= PAGER_LED_CHANNEL_MAX);
}

static bool test_ws2812_uses_grb_byte_order(void) {
    const pager_rgb_t color = {0x12U, 0x34U, 0x56U};

    return pager_led_pack_rgb(color) == 0x34125600U;
}

static void test_running_is_red_and_everything_else_is_white(void) {
    const pager_rgb_t red = {PAGER_LED_CHANNEL_MAX, 0U, 0U};
    const pager_rgb_t white = {8U, 8U, 8U};
    const pager_rgb_t running = pager_led_sample(PAGER_RUNNING, 0U);
    const pager_rgb_t multi = pager_led_sample(PAGER_MULTI, 5000U);
    int state;

    assert(memcmp(&running, &red, sizeof(red)) == 0);
    assert(memcmp(&multi, &red, sizeof(red)) == 0);

    for (state = PAGER_IDLE; state <= PAGER_OFFLINE; ++state) {
        pager_rgb_t actual;

        if (state == PAGER_RUNNING || state == PAGER_MULTI) {
            continue;
        }
        actual = pager_led_sample((pager_state_t)state, 5000U);
        assert(memcmp(&actual, &white, sizeof(white)) == 0);
    }
}

static void test_every_led_sample_is_bounded(void) {
    int state;
    uint32_t elapsed_ms;

    for (state = PAGER_IDLE; state <= PAGER_OFFLINE; ++state) {
        for (elapsed_ms = 0U; elapsed_ms < 10000U; elapsed_ms += 37U) {
            assert_bounded(pager_led_sample((pager_state_t)state, elapsed_ms));
        }
    }
}

static void test_display_pattern_colors_and_orientation_markers(void) {
    assert(pager_rgb565(255U, 0U, 0U) == 0xF800U);
    assert(pager_rgb565(0U, 255U, 0U) == 0x07E0U);
    assert(pager_rgb565(0U, 0U, 255U) == 0x001FU);
    assert(pager_display_test_color(60U, 60U) == 0xF800U);
    assert(pager_display_test_color(180U, 60U) == 0x07E0U);
    assert(pager_display_test_color(60U, 180U) == 0x001FU);
    assert(pager_display_test_color(180U, 180U) == 0xFFFFU);
    assert(pager_display_test_color(10U, 10U) == pager_rgb565(255U, 220U, 0U));
    assert(pager_display_test_color(230U, 10U) == pager_rgb565(0U, 220U, 255U));
    assert(pager_display_test_color(0U, 0U) == 0x0000U);
}

static void test_display_uses_merchant_panel_profile(void) {
    size_t index;
    int found_pixel_format = 0;
    int found_positive_gamma = 0;
    int found_negative_gamma = 0;

    for (index = 0U; index < g_st7789_vendor_init_count; ++index) {
        const st7789_init_step_t *step = &g_st7789_vendor_init[index];
        if (step->command == 0x3AU) {
            found_pixel_format = step->length == 1U && step->data[0] == 0x05U;
        } else if (step->command == 0xE0U) {
            found_positive_gamma = step->length == 14U;
        } else if (step->command == 0xE1U) {
            found_negative_gamma = step->length == 14U;
        }
    }

    assert(found_pixel_format);
    assert(found_positive_gamma);
    assert(found_negative_gamma);
}

static void test_running_pose_has_motion_and_strong_scale_change(void) {
    const pager_scene_pose_t start = pager_scene_pose(PAGER_RUNNING, 0U);
    const pager_scene_pose_t quarter = pager_scene_pose(PAGER_RUNNING, 1175U);
    const pager_scene_pose_t half = pager_scene_pose(PAGER_RUNNING, 2350U);

    assert(start.angle != quarter.angle);
    assert(quarter.angle != half.angle);
    assert(half.scale_q12 > start.scale_q12 + 1500U);
}

static void test_done_pose_pops_every_three_seconds(void) {
    const pager_scene_pose_t start = pager_scene_pose(PAGER_DONE, 0U);
    const pager_scene_pose_t compressed = pager_scene_pose(PAGER_DONE, 180U);
    const pager_scene_pose_t expanded = pager_scene_pose(PAGER_DONE, 390U);
    const pager_scene_pose_t repeated = pager_scene_pose(PAGER_DONE, 3000U);

    assert(compressed.scale_q12 < start.scale_q12);
    assert(expanded.scale_q12 > start.scale_q12);
    assert(repeated.scale_q12 == start.scale_q12);
    assert(repeated.ring_radius == start.ring_radius);
}

static void test_logo_rotation_keeps_exact_center_sample(void) {
    const uint8_t center = pager_scene_sample_logo(
        PAGER_SCENE_CENTER_X, PAGER_SCENE_CENTER_Y, 0U, 4096U);
    uint16_t angle;

    assert(center == 0U);
    for (angle = 1U; angle < 256U; ++angle) {
        assert(pager_scene_sample_logo(
                   PAGER_SCENE_CENTER_X,
                   PAGER_SCENE_CENTER_Y,
                   (uint8_t)angle,
                   4096U) == center);
    }
}

static void test_state_palette_is_not_monochrome(void) {
    const uint16_t base = pager_scene_base_color(PAGER_RUNNING);
    const uint16_t logo = pager_scene_logo_color(PAGER_RUNNING);
    const uint16_t ring = pager_scene_ring_color(PAGER_RUNNING);
    const uint16_t base_red = (base >> 11U) & 0x1FU;
    const uint16_t base_green = (base >> 5U) & 0x3FU;
    const uint16_t base_blue = base & 0x1FU;
    const uint16_t logo_red = (logo >> 11U) & 0x1FU;
    const uint16_t logo_green = (logo >> 5U) & 0x3FU;
    const uint16_t logo_blue = logo & 0x1FU;
    const uint16_t ring_red = (ring >> 11U) & 0x1FU;
    const uint16_t ring_green = (ring >> 5U) & 0x3FU;
    const uint16_t ring_blue = ring & 0x1FU;

    assert(pager_scene_base_color(PAGER_RUNNING) ==
           pager_scene_base_color(PAGER_DONE));
    assert(pager_scene_logo_color(PAGER_RUNNING) !=
           pager_scene_ring_color(PAGER_RUNNING));
    assert(pager_scene_logo_color(PAGER_RUNNING) !=
           pager_scene_logo_color(PAGER_DONE));
    assert(pager_scene_ring_color(PAGER_DONE) !=
           pager_scene_ring_color(PAGER_WAIT));
    assert(base_red <= 2U);
    assert(base_green <= 4U);
    assert(base_blue >= 3U);
    assert(logo_blue >= 28U);
    assert(logo_red * 2U > logo_green);
    assert(logo_green <= 8U);
    assert(ring_blue >= 28U);
    assert(ring_green > ring_red * 2U);
    assert(ring_green <= 20U);
}

static void test_dynamic_background_fades_before_region_edges(void) {
    const uint16_t base = pager_scene_base_color(PAGER_RUNNING);
    const uint16_t center = pager_scene_background_color(
        PAGER_RUNNING, 0U, PAGER_SCENE_CENTER_X, PAGER_SCENE_CENTER_Y);

    assert(center != base);
    assert(pager_scene_background_color(
               PAGER_RUNNING,
               0U,
               PAGER_SCENE_REGION_X,
               PAGER_SCENE_CENTER_Y) == base);
    assert(pager_scene_background_color(
               PAGER_RUNNING,
               0U,
               PAGER_SCENE_CENTER_X,
               PAGER_SCENE_REGION_Y) == base);
}

static void test_animation_targets_sixty_fps(void) {
    assert(PAGER_SCENE_FRAME_MS == 16U);
}

static void test_state_transition_uses_smooth_monotonic_easing(void) {
    uint32_t elapsed;
    uint8_t previous = 0U;

    assert(PAGER_SCENE_TRANSITION_MS == 650U);
    assert(pager_scene_transition_alpha(0U) == 0U);
    assert(pager_scene_transition_alpha(325U) >= 127U);
    assert(pager_scene_transition_alpha(325U) <= 128U);
    assert(pager_scene_transition_alpha(650U) == 255U);
    assert(pager_scene_transition_alpha(1000U) == 255U);

    for (elapsed = 0U; elapsed <= PAGER_SCENE_TRANSITION_MS; ++elapsed) {
        const uint8_t alpha = pager_scene_transition_alpha(elapsed);
        assert(alpha >= previous);
        previous = alpha;
    }
}

static void assert_all_piece_colors(
    const pager_blossom_model_t *model, uint16_t color) {
    uint8_t piece;

    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        assert(model->pieces[piece].color == color);
    }
}

static void test_ready_to_running_crossfades_without_pause(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t start;
    pager_blossom_model_t first_visible_frame;
    pager_blossom_model_t middle;
    pager_blossom_model_t finish;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 1000U);
    pager_blossom_motion_set_target(&motion, PAGER_RUNNING, 1000U);
    pager_blossom_motion_sample(&motion, 1000U, &start);
    pager_blossom_motion_sample(&motion, 1016U, &first_visible_frame);
    pager_blossom_motion_sample(&motion, 1720U, &middle);
    pager_blossom_motion_sample(&motion, 1800U, &finish);

    assert(PAGER_READY_TO_RUNNING_MS == 800U);
    assert(start.pieces[0].color == PAGER_BLOSSOM_READY_COLOR);
    assert(first_visible_frame.pieces[0].color !=
           PAGER_BLOSSOM_READY_COLOR);
    assert(first_visible_frame.pieces[0].center_y_q8 >
           start.pieces[0].center_y_q8);
    assert(start.petal_layer_opacity == 255U);
    assert(start.full_layer_opacity == 0U);
    assert(middle.petal_layer_opacity > 0U);
    assert(middle.full_layer_opacity > 0U);
    assert(finish.petal_layer_opacity == 0U);
    assert(finish.full_layer_opacity == 255U);
    assert(finish.pieces[0].scale_q12 == start.pieces[0].scale_q12);
}

static void test_ready_to_running_keeps_gathering_during_crossfade(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t previous;
    uint32_t elapsed;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 1000U);
    pager_blossom_motion_set_target(&motion, PAGER_RUNNING, 1000U);
    pager_blossom_motion_sample(&motion, 1520U, &previous);
    for (elapsed = 1552U; elapsed <= 1744U; elapsed += 32U) {
        pager_blossom_model_t current;

        pager_blossom_motion_sample(&motion, elapsed, &current);
        assert(
            current.pieces[0].center_x_q8 != previous.pieces[0].center_x_q8 ||
            current.pieces[0].center_y_q8 != previous.pieces[0].center_y_q8 ||
            current.pieces[0].angle_q8 != previous.pieces[0].angle_q8);
        assert(current.full_layer_opacity >= previous.full_layer_opacity);
        previous = current;
    }
}

static void test_running_motion_accelerates_and_breathes_without_stopping(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t previous;
    uint16_t minimum_scale = UINT16_MAX;
    uint16_t maximum_scale = 0U;
    uint8_t minimum_step = UINT8_MAX;
    uint8_t maximum_step = 0U;
    uint32_t elapsed_ms;

    pager_blossom_motion_init(&motion, PAGER_RUNNING, 0U);
    pager_blossom_motion_sample(&motion, 0U, &previous);
    for (elapsed_ms = 16U; elapsed_ms <= 2600U; elapsed_ms += 16U) {
        pager_blossom_model_t current;
        const uint8_t previous_angle =
            (uint8_t)((uint16_t)previous.pieces[0].angle_q8 >> 8U);
        uint8_t current_angle;
        uint8_t step;

        pager_blossom_motion_sample(&motion, elapsed_ms, &current);
        current_angle =
            (uint8_t)((uint16_t)current.pieces[0].angle_q8 >> 8U);
        step = (uint8_t)(current_angle - previous_angle);
        assert(step > 0U);
        if (step < minimum_step) {
            minimum_step = step;
        }
        if (step > maximum_step) {
            maximum_step = step;
        }
        if (current.pieces[0].scale_q12 < minimum_scale) {
            minimum_scale = current.pieces[0].scale_q12;
        }
        if (current.pieces[0].scale_q12 > maximum_scale) {
            maximum_scale = current.pieces[0].scale_q12;
        }
        previous = current;
    }
    assert(maximum_step > minimum_step);
    assert(maximum_scale > minimum_scale + 1000U);
}

static void test_running_to_ready_reverses_crossfade(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t middle;
    pager_blossom_model_t finish;

    pager_blossom_motion_init(&motion, PAGER_RUNNING, 2000U);
    pager_blossom_motion_set_target(&motion, PAGER_IDLE, 2000U);
    pager_blossom_motion_sample(&motion, 2300U, &middle);
    pager_blossom_motion_sample(
        &motion, 2000U + PAGER_RUNNING_TO_READY_MS, &finish);

    assert(middle.petal_layer_opacity > 0U);
    assert(middle.full_layer_opacity > 0U);
    assert(middle.full_layer_color == PAGER_BLOSSOM_RUNNING_COLOR);
    assert_all_piece_colors(&middle, PAGER_BLOSSOM_READY_COLOR);
    assert(finish.petal_layer_opacity == 255U);
    assert(finish.full_layer_opacity == 0U);
    assert(finish.balance_opacity == 255U);
    assert(finish.ordered_orbit);
}

static void test_offline_to_ready_never_uses_full_layer(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t middle;

    pager_blossom_motion_init(&motion, PAGER_OFFLINE, 3000U);
    pager_blossom_motion_set_target(&motion, PAGER_IDLE, 3000U);
    pager_blossom_motion_sample(&motion, 3600U, &middle);

    assert(middle.petal_layer_opacity == 255U);
    assert(middle.full_layer_opacity == 0U);
}

static void test_offline_petals_fall_and_settle_at_hexagon_bottom(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t start;
    pager_blossom_model_t settled;
    pager_blossom_model_t later;
    uint8_t piece;

    pager_blossom_motion_init(&motion, PAGER_OFFLINE, 0U);
    pager_blossom_motion_sample(&motion, 0U, &start);
    pager_blossom_motion_sample(&motion, 1400U, &settled);
    pager_blossom_motion_sample(&motion, 5000U, &later);
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        assert(settled.pieces[piece].center_y_q8 >
               start.pieces[piece].center_y_q8);
        assert(settled.pieces[piece].center_y_q8 >= 148 * 256);
        assert(settled.pieces[piece].color ==
               PAGER_BLOSSOM_OFFLINE_COLOR);
        assert(settled.pieces[piece].center_x_q8 ==
               later.pieces[piece].center_x_q8);
        assert(settled.pieces[piece].center_y_q8 ==
               later.pieces[piece].center_y_q8);
        assert(settled.pieces[piece].angle_q8 ==
               later.pieces[piece].angle_q8);
    }
}

static void test_wait_state_uses_amber_double_pulse(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t rest;
    pager_blossom_model_t first_peak;
    pager_blossom_model_t gap;
    pager_blossom_model_t second_peak;

    pager_blossom_motion_init(&motion, PAGER_WAIT, 0U);
    pager_blossom_motion_sample(&motion, 0U, &rest);
    pager_blossom_motion_sample(&motion, 90U, &first_peak);
    pager_blossom_motion_sample(&motion, 220U, &gap);
    pager_blossom_motion_sample(&motion, 350U, &second_peak);

    assert(rest.full_layer_opacity == 255U);
    assert(rest.petal_layer_opacity == 0U);
    assert(rest.full_layer_color == PAGER_BLOSSOM_WAIT_COLOR);
    assert(first_peak.pieces[0].scale_q12 > rest.pieces[0].scale_q12);
    assert(gap.pieces[0].scale_q12 == rest.pieces[0].scale_q12);
    assert(second_peak.pieces[0].scale_q12 >
           rest.pieces[0].scale_q12);
}

static void test_ready_keeps_all_six_piece_centers_on_screen(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t ready;
    uint8_t piece;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 0U);
    pager_blossom_motion_sample(&motion, 0U, &ready);
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        const int32_t dx_q8 =
            ready.pieces[piece].center_x_q8 - 120 * 256;
        const int32_t dy_q8 =
            ready.pieces[piece].center_y_q8 - 120 * 256;
        const int32_t radius2_q16 =
            (int32_t)(((int64_t)dx_q8 * dx_q8 +
                       (int64_t)dy_q8 * dy_q8) >> 16U);
        const uint8_t expected_angle =
            (uint8_t)(192U + 32U -
                ((uint16_t)piece * 256U) / BLOSSOM_PIECE_COUNT);
        uint8_t other;

        assert(ready.pieces[piece].center_x_q8 >= 0);
        assert(ready.pieces[piece].center_x_q8 <= 239 * 256);
        assert(ready.pieces[piece].center_y_q8 >= 0);
        assert(ready.pieces[piece].center_y_q8 <= 239 * 256);
        assert(ready.pieces[piece].scale_q12 == 3604U);
        assert(radius2_q16 >= 67 * 67);
        assert(radius2_q16 <= 69 * 69);
        assert((uint8_t)((uint16_t)ready.pieces[piece].angle_q8 >> 8U) ==
               expected_angle);
        for (other = (uint8_t)(piece + 1U);
             other < BLOSSOM_PIECE_COUNT;
             ++other) {
            assert(
                ready.pieces[piece].center_x_q8 !=
                    ready.pieces[other].center_x_q8 ||
                ready.pieces[piece].center_y_q8 !=
                    ready.pieces[other].center_y_q8);
        }
    }
}

static void test_ready_prepares_one_composite_layer(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t ready;
    pager_scene_render_context_t context;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 0U);
    pager_blossom_motion_sample(&motion, 0U, &ready);
    pager_scene_prepare_render_context(
        &ready, "82", 0U, NULL, 0U, &context);

    assert(!context.petals_visible);
    assert(context.full_visible);
    assert(context.full.mask_4bpp == g_blossom_ready_alpha_4bpp);
    assert(context.full.mask_size == BLOSSOM_READY_MASK_SIZE);
}

static void test_ready_orbit_advances_on_every_sixteen_ms_frame(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t previous;
    uint32_t elapsed_ms;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 0U);
    pager_blossom_motion_sample(&motion, 0U, &previous);
    for (elapsed_ms = 16U; elapsed_ms <= 160U; elapsed_ms += 16U) {
        pager_blossom_model_t current;

        pager_blossom_motion_sample(&motion, elapsed_ms, &current);
        assert(current.pieces[0].angle_q8 !=
               previous.pieces[0].angle_q8);
        assert(current.pieces[0].center_x_q8 !=
                   previous.pieces[0].center_x_q8 ||
               current.pieces[0].center_y_q8 !=
                   previous.pieces[0].center_y_q8);
        previous = current;
    }
}

static void test_ready_piece_clips_are_small_and_inside_scene(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t ready;
    pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT];
    uint32_t elapsed_ms;
    uint8_t piece;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 0U);
    for (elapsed_ms = 0U; elapsed_ms < 18000U; elapsed_ms += 750U) {
        pager_blossom_motion_sample(&motion, elapsed_ms, &ready);
        pager_scene_prepare_motion(&ready, clips);
        for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
            assert(clips[piece].left > PAGER_SCENE_REGION_X);
            assert(clips[piece].top > PAGER_SCENE_REGION_Y);
            assert(clips[piece].right <
                   PAGER_SCENE_REGION_X + PAGER_SCENE_REGION_SIZE - 1U);
            assert(clips[piece].bottom <
                   PAGER_SCENE_REGION_Y + PAGER_SCENE_REGION_SIZE - 1U);
            assert(clips[piece].right - clips[piece].left < 110);
            assert(clips[piece].bottom - clips[piece].top < 110);
        }
    }
}

static uint8_t count_bits_u8(uint8_t value) {
    uint8_t count = 0U;

    while (value != 0U) {
        count = (uint8_t)(count + (value & 1U));
        value >>= 1U;
    }
    return count;
}

static void test_ready_motion_marks_only_touched_tiles(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t previous;
    pager_blossom_model_t current;
    pager_scene_piece_clip_t previous_clips[BLOSSOM_PIECE_COUNT];
    pager_scene_piece_clip_t current_clips[BLOSSOM_PIECE_COUNT];
    pager_scene_tile_map_t dirty;
    uint16_t dirty_count = 0U;
    uint8_t tile_y;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 0U);
    pager_blossom_motion_sample(&motion, 0U, &previous);
    pager_blossom_motion_sample(&motion, 16U, &current);
    pager_scene_prepare_motion(&previous, previous_clips);
    pager_scene_prepare_motion(&current, current_clips);
    pager_scene_mark_motion_tiles(
        &previous, previous_clips, &current, current_clips, &dirty);

    for (tile_y = 0U; tile_y < PAGER_SCENE_TILE_COUNT; ++tile_y) {
        uint8_t tile_x;

        for (tile_x = 0U; tile_x < PAGER_SCENE_TILE_COUNT; ++tile_x) {
            dirty_count += pager_scene_tile_dirty(&dirty, tile_x, tile_y);
        }
    }
    assert(dirty_count > 0U);
    assert(dirty_count < PAGER_SCENE_TILE_COUNT * PAGER_SCENE_TILE_COUNT);
    assert(!pager_scene_tile_dirty(&dirty, 0U, 0U));
    assert(!pager_scene_tile_dirty(
        &dirty,
        PAGER_SCENE_TILE_COUNT - 1U,
        PAGER_SCENE_TILE_COUNT - 1U));
}

static void test_ready_tile_checks_only_intersecting_petals(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t ready;
    pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT];
    uint8_t piece;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 0U);
    pager_blossom_motion_sample(&motion, 0U, &ready);
    pager_scene_prepare_motion(&ready, clips);
    assert(pager_scene_tile_layer_mask(&ready, clips, 0U, 0U) == 0U);

    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        const int16_t center_x =
            (int16_t)((ready.pieces[piece].center_x_q8 + 128) >> 8U);
        const int16_t center_y =
            (int16_t)((ready.pieces[piece].center_y_q8 + 128) >> 8U);
        const uint8_t tile_x = (uint8_t)(
            (center_x - PAGER_SCENE_REGION_X) / PAGER_SCENE_TILE_SIZE);
        const uint8_t tile_y = (uint8_t)(
            (center_y - PAGER_SCENE_REGION_Y) / PAGER_SCENE_TILE_SIZE);
        const uint8_t mask = pager_scene_tile_layer_mask(
            &ready, clips, tile_x, tile_y);

        assert((mask & (uint8_t)(1U << piece)) != 0U);
        assert(count_bits_u8(mask) < BLOSSOM_PIECE_COUNT);
    }
}

static void assert_tiled_render_matches_full_render(
    pager_state_t state,
    uint32_t elapsed_ms,
    const pager_blossom_model_t *model) {
    pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT];
    uint16_t full_row[PAGER_SCENE_REGION_SIZE];
    uint16_t tile_row[PAGER_SCENE_TILE_SIZE];
    uint8_t tile_y;

    pager_scene_prepare_motion(model, clips);
    for (tile_y = 0U; tile_y < PAGER_SCENE_TILE_COUNT; ++tile_y) {
        uint16_t row;

        for (row = 0U; row < PAGER_SCENE_TILE_SIZE; ++row) {
            const int16_t y = (int16_t)(
                PAGER_SCENE_REGION_Y +
                tile_y * PAGER_SCENE_TILE_SIZE + row);
            uint8_t tile_x;

            pager_scene_render_motion_row(
                state, elapsed_ms, model, clips, "82", y, full_row);
            for (tile_x = 0U;
                 tile_x < PAGER_SCENE_TILE_COUNT;
                 ++tile_x) {
                const uint8_t piece_mask = pager_scene_tile_layer_mask(
                    model, clips, tile_x, tile_y);
                const bool full_active =
                    pager_scene_tile_full_layer_active(
                        model, tile_x, tile_y);

                pager_scene_render_motion_span(
                    state,
                    elapsed_ms,
                    model,
                    piece_mask,
                    full_active,
                    "82",
                    (int16_t)(
                        PAGER_SCENE_REGION_X +
                        tile_x * PAGER_SCENE_TILE_SIZE),
                    y,
                    PAGER_SCENE_TILE_SIZE,
                    tile_row);
                if (memcmp(
                        tile_row,
                        &full_row[tile_x * PAGER_SCENE_TILE_SIZE],
                        sizeof(tile_row)) != 0) {
                    uint8_t column;

                    for (column = 0U;
                         column < PAGER_SCENE_TILE_SIZE;
                         ++column) {
                        if (tile_row[column] !=
                            full_row[
                                tile_x * PAGER_SCENE_TILE_SIZE + column]) {
                            fprintf(
                                stderr,
                                "tile mismatch state=%d tile=%u,%u "
                                "row=%u column=%u mask=0x%02x full=%d "
                                "expected=0x%04x actual=0x%04x\n",
                                (int)state,
                                tile_x,
                                tile_y,
                                row,
                                column,
                                piece_mask,
                                full_active,
                                full_row[
                                    tile_x * PAGER_SCENE_TILE_SIZE + column],
                                tile_row[column]);
                            break;
                        }
                    }
                    assert(false);
                }
            }
        }
    }
}

static void test_ready_composite_is_active_inside_sparse_tiles(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t ready;
    pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT];
    uint8_t piece;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 0U);
    pager_blossom_motion_sample(&motion, 1000U, &ready);
    pager_scene_prepare_motion(&ready, clips);
    assert(ready.ordered_orbit);
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        const int16_t center_x =
            (int16_t)((ready.pieces[piece].center_x_q8 + 128) >> 8U);
        const int16_t center_y =
            (int16_t)((ready.pieces[piece].center_y_q8 + 128) >> 8U);
        const uint8_t tile_x = (uint8_t)(
            (center_x - PAGER_SCENE_REGION_X) / PAGER_SCENE_TILE_SIZE);
        const uint8_t tile_y = (uint8_t)(
            (center_y - PAGER_SCENE_REGION_Y) / PAGER_SCENE_TILE_SIZE);

        assert(pager_scene_tile_full_layer_active(
            &ready, tile_x, tile_y));
    }
}

static void test_tiled_renderer_matches_crossfade_pixels(void) {
    pager_blossom_motion_t motion;
    pager_blossom_model_t crossfade;

    pager_blossom_motion_init(&motion, PAGER_IDLE, 0U);
    pager_blossom_motion_set_target(&motion, PAGER_RUNNING, 2000U);
    pager_blossom_motion_sample(&motion, 2720U, &crossfade);
    assert(crossfade.petal_layer_opacity != 0U);
    assert(crossfade.full_layer_opacity != 0U);
    assert_tiled_render_matches_full_render(
        PAGER_RUNNING, 720U, &crossfade);
}

static void test_pointy_hexagon_reaches_screen_top_and_bottom(void) {
    assert(pager_scene_is_hex_outline(120, 0));
    assert(pager_scene_is_hex_outline(120, 239));
    assert(pager_scene_is_hex_outline(16, 60));
    assert(pager_scene_is_hex_outline(224, 60));
    assert(pager_scene_is_hex_outline(16, 180));
    assert(pager_scene_is_hex_outline(224, 180));
    assert(!pager_scene_is_hex_outline(120, 120));
    assert(!pager_scene_is_hex_outline(35, 120));
}

static void test_six_piece_masks_are_identical_and_nonempty(void) {
    uint8_t piece;

    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        int samples = 0;
        int16_t y;

        if (piece > 0U) {
            assert(memcmp(
                g_blossom_piece_alpha_4bpp[0],
                g_blossom_piece_alpha_4bpp[piece],
                BLOSSOM_MASK_BYTES) == 0);
        }
        for (y = 50; y < 190; y += 2) {
            int16_t x;
            for (x = 50; x < 190; x += 2) {
                samples += pager_scene_sample_piece_logo(
                    x, y, 0U, 3604U, piece) != 0U;
            }
        }
        assert(samples > 20);
    }
}

static void test_idle_balance_layout_is_centered(void) {
    const pager_idle_layout_t one = pager_scene_idle_layout("8");
    const pager_idle_layout_t two = pager_scene_idle_layout("88");
    const pager_idle_layout_t three = pager_scene_idle_layout("100");

    assert(one.visible);
    assert(two.visible);
    assert(three.visible);
    assert(one.value_center_x == PAGER_SCENE_CENTER_X);
    assert(two.value_center_x == PAGER_SCENE_CENTER_X);
    assert(three.value_center_x == PAGER_SCENE_CENTER_X);
    assert(three.value_left >= PAGER_SCENE_REGION_X);
    assert(three.value_right <
           PAGER_SCENE_REGION_X + PAGER_SCENE_REGION_SIZE);
    assert(!pager_scene_idle_layout("NA").visible);
}

static void test_non_idle_scene_ignores_balance(void) {
    uint16_t without_balance[PAGER_SCENE_REGION_SIZE];
    uint16_t with_balance[PAGER_SCENE_REGION_SIZE];

    pager_scene_render_row(
        PAGER_RUNNING, 500U, "NA", 160, without_balance);
    pager_scene_render_row(
        PAGER_RUNNING, 500U, "88", 160, with_balance);
    assert(memcmp(without_balance, with_balance, sizeof(with_balance)) == 0);
}

static void test_idle_scene_renders_known_balance(void) {
    uint16_t without_balance[PAGER_SCENE_REGION_SIZE];
    uint16_t with_balance[PAGER_SCENE_REGION_SIZE];

    pager_scene_render_row(
        PAGER_IDLE, 500U, "NA", 154, without_balance);
    pager_scene_render_row(
        PAGER_IDLE, 500U, "88", 154, with_balance);
    assert(memcmp(without_balance, with_balance, sizeof(with_balance)) != 0);
}

typedef struct {
    const char *bytes;
    size_t offset;
} stream_fixture_t;

static int read_fixture_byte(void *context) {
    stream_fixture_t *fixture = context;
    const unsigned char byte = (unsigned char)fixture->bytes[fixture->offset];

    if (byte == '\0') {
        return PAGER_STREAM_NO_BYTE;
    }
    ++fixture->offset;
    return byte;
}

static void test_stream_drain_consumes_all_pending_snapshots(void) {
    stream_fixture_t fixture = {
        "STATE RUNNING RUN=1 WAIT=0 DONE=2 BAL=81 EV=NONE\n"
        "STATE DONE RUN=0 WAIT=0 DONE=3 BAL=80 EV=DONE\n",
        0U,
    };
    pager_stream_t stream = {{0}, 0U};
    pager_snapshot_t latest = {0};

    assert(pager_stream_drain(
               &stream, read_fixture_byte, &fixture, &latest) == 2U);
    assert(latest.state == PAGER_DONE);
    assert(latest.done == 3U);
    assert(strcmp(latest.balance, "80") == 0);
    assert(fixture.bytes[fixture.offset] == '\0');
}

int main(void) {
#define RUN_TEST(test_name)        \
    do {                           \
        puts("RUN " #test_name);   \
        fflush(stdout);            \
        test_name();               \
    } while (0)

    RUN_TEST(test_valid_multi_snapshot);
    RUN_TEST(test_display_ghost_count_caps_additional_tasks);
    RUN_TEST(test_ghost_count_transition_fades_only_changed_layers);
    RUN_TEST(test_buzzer_event_pulse_counts_and_nonblocking_timing);
    RUN_TEST(test_wait_priority_and_timeout);
    RUN_TEST(test_event_and_state_priority);
    RUN_TEST(test_done_and_idle_selection);
    RUN_TEST(test_balance_parser_boundaries);
    RUN_TEST(test_invalid_lines_are_rejected);
    RUN_TEST(test_timeout_handles_millisecond_wraparound);
    if (!test_ws2812_uses_grb_byte_order()) {
        fputs("WS2812 byte order is not GRB\n", stderr);
        return 1;
    }
    RUN_TEST(test_running_is_red_and_everything_else_is_white);
    RUN_TEST(test_every_led_sample_is_bounded);
    RUN_TEST(test_display_pattern_colors_and_orientation_markers);
    RUN_TEST(test_display_uses_merchant_panel_profile);
    RUN_TEST(test_running_pose_has_motion_and_strong_scale_change);
    RUN_TEST(test_done_pose_pops_every_three_seconds);
    RUN_TEST(test_logo_rotation_keeps_exact_center_sample);
    RUN_TEST(test_state_palette_is_not_monochrome);
    RUN_TEST(test_dynamic_background_fades_before_region_edges);
    RUN_TEST(test_animation_targets_sixty_fps);
    RUN_TEST(test_state_transition_uses_smooth_monotonic_easing);
    RUN_TEST(test_ready_to_running_crossfades_without_pause);
    RUN_TEST(test_ready_to_running_keeps_gathering_during_crossfade);
    RUN_TEST(test_running_motion_accelerates_and_breathes_without_stopping);
    RUN_TEST(test_running_to_ready_reverses_crossfade);
    RUN_TEST(test_offline_to_ready_never_uses_full_layer);
    RUN_TEST(test_offline_petals_fall_and_settle_at_hexagon_bottom);
    RUN_TEST(test_wait_state_uses_amber_double_pulse);
    RUN_TEST(test_ready_keeps_all_six_piece_centers_on_screen);
    RUN_TEST(test_ready_orbit_advances_on_every_sixteen_ms_frame);
    RUN_TEST(test_ready_piece_clips_are_small_and_inside_scene);
    RUN_TEST(test_ready_prepares_one_composite_layer);
    RUN_TEST(test_ready_motion_marks_only_touched_tiles);
    RUN_TEST(test_ready_tile_checks_only_intersecting_petals);
    RUN_TEST(test_ready_composite_is_active_inside_sparse_tiles);
    RUN_TEST(test_tiled_renderer_matches_crossfade_pixels);
    RUN_TEST(test_pointy_hexagon_reaches_screen_top_and_bottom);
    RUN_TEST(test_six_piece_masks_are_identical_and_nonempty);
    RUN_TEST(test_idle_balance_layout_is_centered);
    RUN_TEST(test_non_idle_scene_ignores_balance);
    RUN_TEST(test_idle_scene_renders_known_balance);
    RUN_TEST(test_stream_drain_consumes_all_pending_snapshots);
#undef RUN_TEST
    puts("pager core tests passed");
    return 0;
}
