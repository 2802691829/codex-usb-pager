#include "display_ui.h"

#include "board_config.h"
#include "display_scene.h"
#include "st7789.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define SCENE_PIXEL_COUNT \
    (PAGER_SCENE_REGION_SIZE * PAGER_SCENE_REGION_SIZE)
#define RUNNING_DELTA_ROWS 8U

typedef struct {
    uint16_t pixels[SCENE_PIXEL_COUNT];
} scene_frame_t;

static pager_state_t current_state;
static uint32_t state_started_ms;
static uint32_t last_frame_ms;
static bool initialized;
static bool has_front_frame;
static uint8_t front_frame_index;
static char current_balance[PAGER_BALANCE_CAPACITY];
static pager_blossom_motion_t blossom_motion;
static scene_frame_t frame_buffers[2];
static pager_blossom_model_t front_model;
static pager_scene_piece_clip_t front_clips[BLOSSOM_PIECE_COUNT];
static pager_state_t rendered_state;
static bool has_front_model;
static bool balance_dirty;
static uint8_t ghost_from_count;
static uint8_t ghost_to_count;
static uint32_t ghost_transition_started_ms;

static bool copy_balance(const char *balance) {
    char next[PAGER_BALANCE_CAPACITY];
    size_t length = 0U;

    if (balance == NULL) {
        balance = "NA";
    }
    while (length + 1U < sizeof(next) && balance[length] != '\0') {
        next[length] = balance[length];
        ++length;
    }
    next[length] = '\0';
    if (strcmp(next, current_balance) == 0) {
        return false;
    }
    memcpy(current_balance, next, length + 1U);
    return true;
}

static bool is_running_family(pager_state_t state) {
    return state == PAGER_RUNNING || state == PAGER_MULTI;
}

static uint8_t render_ghost_count(void) {
    return ghost_from_count > ghost_to_count
        ? ghost_from_count
        : ghost_to_count;
}

static void current_ghost_opacity(uint32_t now_ms, uint8_t opacity[3]) {
    pager_scene_ghost_opacity(
        ghost_from_count,
        ghost_to_count,
        now_ms - ghost_transition_started_ms,
        opacity);
}

static void render_scene(
    scene_frame_t *destination,
    uint32_t now_ms,
    const pager_blossom_model_t *model,
    const pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT]) {
    pager_scene_render_context_t render_context;
    uint8_t ghost_opacity[PAGER_MULTI_GHOST_MAX];
    int16_t y;
    uint16_t row_index = 0U;

    (void)clips;
    current_ghost_opacity(now_ms, ghost_opacity);
    pager_scene_prepare_render_context(
        model,
        current_balance,
        render_ghost_count(),
        ghost_opacity,
        now_ms,
        &render_context);
    for (y = PAGER_SCENE_REGION_Y;
         y < PAGER_SCENE_REGION_Y + (int16_t)PAGER_SCENE_REGION_SIZE;
         ++y) {
        pager_scene_render_prepared_span(
            current_state,
            now_ms - state_started_ms,
            &render_context,
            (uint8_t)((1U << BLOSSOM_PIECE_COUNT) - 1U),
            true,
            PAGER_SCENE_REGION_X,
            y,
            PAGER_SCENE_REGION_SIZE,
            &destination->pixels[
                (size_t)row_index * PAGER_SCENE_REGION_SIZE]);
        ++row_index;
    }
}

static void send_frame(scene_frame_t *source) {
    size_t row;

    st7789_begin_pixels(
        PAGER_SCENE_REGION_X,
        PAGER_SCENE_REGION_Y,
        PAGER_SCENE_REGION_X + PAGER_SCENE_REGION_SIZE - 1U,
        PAGER_SCENE_REGION_Y + PAGER_SCENE_REGION_SIZE - 1U);
    for (row = 0U; row < PAGER_SCENE_REGION_SIZE; ++row) {
        st7789_write_pixels(
            &source->pixels[row * PAGER_SCENE_REGION_SIZE],
            PAGER_SCENE_REGION_SIZE);
    }
    st7789_wait_idle();
}

static void send_delta_frame(
    const scene_frame_t *previous, const scene_frame_t *current) {
    uint16_t band_start;

    for (band_start = 0U;
         band_start < PAGER_SCENE_REGION_SIZE;
         band_start += RUNNING_DELTA_ROWS) {
        const uint16_t band_end = (uint16_t)(
            band_start + RUNNING_DELTA_ROWS < PAGER_SCENE_REGION_SIZE
                ? band_start + RUNNING_DELTA_ROWS
                : PAGER_SCENE_REGION_SIZE);
        uint16_t first_changed = band_end;
        uint16_t last_changed = band_start;
        uint16_t union_left = PAGER_SCENE_REGION_SIZE;
        uint16_t union_right = 0U;
        uint16_t row;

        for (row = band_start; row < band_end; ++row) {
            const size_t offset =
                (size_t)row * PAGER_SCENE_REGION_SIZE;
            uint16_t left = 0U;
            uint16_t right = PAGER_SCENE_REGION_SIZE;

            while (left < PAGER_SCENE_REGION_SIZE &&
                   previous->pixels[offset + left] ==
                       current->pixels[offset + left]) {
                ++left;
            }
            if (left == PAGER_SCENE_REGION_SIZE) {
                continue;
            }
            while (right > left &&
                   previous->pixels[offset + right - 1U] ==
                       current->pixels[offset + right - 1U]) {
                --right;
            }
            if (left < union_left) {
                union_left = left;
            }
            if (right > union_right) {
                union_right = right;
            }
            if (first_changed == band_end) {
                first_changed = row;
            }
            last_changed = row;
        }
        if (first_changed == band_end) {
            continue;
        }
        st7789_begin_pixels(
            PAGER_SCENE_REGION_X + union_left,
            PAGER_SCENE_REGION_Y + first_changed,
            PAGER_SCENE_REGION_X + union_right - 1U,
            PAGER_SCENE_REGION_Y + last_changed);
        for (row = first_changed; row <= last_changed; ++row) {
            const size_t offset =
                (size_t)row * PAGER_SCENE_REGION_SIZE;
            st7789_write_pixels(
                &current->pixels[offset + union_left],
                union_right - union_left);
        }
    }
    st7789_wait_idle();
}

static void render_dirty_tiles(
    scene_frame_t *frame,
    const pager_scene_tile_map_t *dirty,
    uint32_t now_ms,
    const pager_blossom_model_t *model,
    const pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT]) {
    pager_scene_render_context_t render_context;
    uint8_t ghost_opacity[PAGER_MULTI_GHOST_MAX];
    uint8_t tile_y;

    current_ghost_opacity(now_ms, ghost_opacity);
    pager_scene_prepare_render_context(
        model,
        current_balance,
        render_ghost_count(),
        ghost_opacity,
        now_ms,
        &render_context);
    for (tile_y = 0U; tile_y < PAGER_SCENE_TILE_COUNT; ++tile_y) {
        uint8_t tile_x;

        for (tile_x = 0U; tile_x < PAGER_SCENE_TILE_COUNT; ++tile_x) {
            uint8_t active_piece_mask;
            bool full_layer_active;
            uint16_t pixel_x;
            uint16_t pixel_y;
            uint16_t row;

            if (!pager_scene_tile_dirty(dirty, tile_x, tile_y)) {
                continue;
            }
            active_piece_mask =
                pager_scene_tile_layer_mask(model, clips, tile_x, tile_y);
            full_layer_active =
                pager_scene_tile_full_layer_active(model, tile_x, tile_y);
            pixel_x = (uint16_t)(tile_x * PAGER_SCENE_TILE_SIZE);
            pixel_y = (uint16_t)(tile_y * PAGER_SCENE_TILE_SIZE);
            for (row = 0U; row < PAGER_SCENE_TILE_SIZE; ++row) {
                const size_t offset =
                    (size_t)(pixel_y + row) * PAGER_SCENE_REGION_SIZE +
                    pixel_x;

                pager_scene_render_prepared_span(
                    current_state,
                    now_ms - state_started_ms,
                    &render_context,
                    active_piece_mask,
                    full_layer_active,
                    (int16_t)(PAGER_SCENE_REGION_X + pixel_x),
                    (int16_t)(PAGER_SCENE_REGION_Y + pixel_y + row),
                    PAGER_SCENE_TILE_SIZE,
                    &frame->pixels[offset]);
            }
        }
    }
}

static void send_dirty_tiles(
    const scene_frame_t *frame, const pager_scene_tile_map_t *dirty) {
    uint8_t tile_y;

    for (tile_y = 0U; tile_y < PAGER_SCENE_TILE_COUNT; ++tile_y) {
        uint8_t tile_x = 0U;

        while (tile_x < PAGER_SCENE_TILE_COUNT) {
            uint8_t run_first_tile;
            uint8_t run_last_tile;
            uint16_t first_pixel;
            uint16_t pixel_count;
            uint16_t row;

            while (tile_x < PAGER_SCENE_TILE_COUNT &&
                   !pager_scene_tile_dirty(dirty, tile_x, tile_y)) {
                ++tile_x;
            }
            if (tile_x >= PAGER_SCENE_TILE_COUNT) {
                break;
            }
            run_first_tile = tile_x;
            while (tile_x + 1U < PAGER_SCENE_TILE_COUNT &&
                   pager_scene_tile_dirty(
                       dirty, (uint8_t)(tile_x + 1U), tile_y)) {
                ++tile_x;
            }
            run_last_tile = tile_x;
            first_pixel =
                (uint16_t)(run_first_tile * PAGER_SCENE_TILE_SIZE);
            pixel_count = (uint16_t)(
                (run_last_tile - run_first_tile + 1U) *
                PAGER_SCENE_TILE_SIZE);
            st7789_begin_pixels(
                PAGER_SCENE_REGION_X + first_pixel,
                PAGER_SCENE_REGION_Y +
                    (uint16_t)tile_y * PAGER_SCENE_TILE_SIZE,
                PAGER_SCENE_REGION_X + first_pixel + pixel_count - 1U,
                PAGER_SCENE_REGION_Y +
                    (uint16_t)(tile_y + 1U) * PAGER_SCENE_TILE_SIZE - 1U);
            for (row = 0U; row < PAGER_SCENE_TILE_SIZE; ++row) {
                const size_t offset =
                    ((size_t)tile_y * PAGER_SCENE_TILE_SIZE + row) *
                        PAGER_SCENE_REGION_SIZE +
                    first_pixel;

                st7789_write_pixels(&frame->pixels[offset], pixel_count);
            }
            ++tile_x;
        }
    }
    st7789_wait_idle();
}

static void draw_hex_caps(void) {
    uint16_t row[PAGER_DISPLAY_WIDTH];
    uint16_t y;

    for (y = 0U; y < PAGER_DISPLAY_HEIGHT; ++y) {
        uint16_t x;

        if (y >= PAGER_SCENE_REGION_Y &&
            y < PAGER_SCENE_REGION_Y + PAGER_SCENE_REGION_SIZE) {
            continue;
        }
        for (x = 0U; x < PAGER_DISPLAY_WIDTH; ++x) {
            row[x] = pager_scene_is_hex_outline((int16_t)x, (int16_t)y)
                ? pager_scene_hex_color()
                : pager_scene_base_color(current_state);
        }
        st7789_begin_pixels(0U, y, PAGER_DISPLAY_WIDTH - 1U, y);
        st7789_write_pixels(row, PAGER_DISPLAY_WIDTH);
    }
    st7789_wait_idle();
}

static void render_frame(uint32_t now_ms) {
    pager_blossom_model_t model;
    pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT];
    const uint8_t working_index = (uint8_t)(front_frame_index ^ 1U);
    scene_frame_t *working = &frame_buffers[working_index];
    const bool previous_petals_visible =
        has_front_model && front_model.petal_layer_opacity != 0U;
    const bool previous_individual_petals =
        previous_petals_visible && !front_model.ordered_orbit;
    bool current_petals_visible;
    bool current_ready_composite;

    pager_blossom_motion_sample(&blossom_motion, now_ms, &model);
    pager_scene_prepare_motion(&model, clips);
    current_petals_visible = model.petal_layer_opacity != 0U;
    current_ready_composite =
        model.petal_layer_opacity != 0U && model.ordered_orbit;
    if (!has_front_frame) {
        render_scene(working, now_ms, &model, clips);
        send_frame(working);
        front_frame_index = working_index;
        has_front_frame = true;
    } else if (current_ready_composite && previous_individual_petals) {
        render_scene(working, now_ms, &model, clips);
        send_frame(working);
        front_frame_index = working_index;
    } else if (previous_petals_visible || current_petals_visible) {
        pager_scene_tile_map_t dirty;
        scene_frame_t *front = &frame_buffers[front_frame_index];

        pager_scene_mark_motion_tiles(
            &front_model, front_clips, &model, clips, &dirty);
        if (balance_dirty) {
            pager_scene_mark_balance_tiles(&dirty);
        }
        if (rendered_state != current_state) {
            pager_scene_tile_map_fill(&dirty);
        }
        render_dirty_tiles(front, &dirty, now_ms, &model, clips);
        send_dirty_tiles(front, &dirty);
    } else {
        render_scene(working, now_ms, &model, clips);
        send_delta_frame(&frame_buffers[front_frame_index], working);
        front_frame_index = working_index;
    }
    front_model = model;
    memcpy(front_clips, clips, sizeof(front_clips));
    rendered_state = current_state;
    has_front_model = true;
    balance_dirty = false;
}

void pager_display_ui_init(pager_state_t state, uint32_t now_ms) {
    current_state = state;
    state_started_ms = now_ms;
    last_frame_ms = 0U;
    initialized = true;
    has_front_frame = false;
    has_front_model = false;
    balance_dirty = false;
    ghost_from_count = 0U;
    ghost_to_count = 0U;
    ghost_transition_started_ms = now_ms;
    front_frame_index = 0U;
    current_balance[0] = 'N';
    current_balance[1] = 'A';
    current_balance[2] = '\0';
    pager_blossom_motion_init(&blossom_motion, state, now_ms);
    st7789_fill(pager_scene_base_color(state));
    draw_hex_caps();
    render_frame(now_ms);
    last_frame_ms = now_ms;
}

void pager_display_ui_set_state(pager_state_t state, uint32_t now_ms) {
    pager_display_ui_set_snapshot(state, 0U, current_balance, now_ms);
}

void pager_display_ui_set_snapshot(
    pager_state_t state,
    uint32_t running_count,
    const char *balance,
    uint32_t now_ms) {
    const bool balance_changed = copy_balance(balance);
    const uint8_t next_ghost_count =
        pager_scene_ghost_count(state, running_count);
    const bool running_family_change =
        is_running_family(current_state) && is_running_family(state);

    if (!initialized) {
        return;
    }
    if (balance_changed) {
        balance_dirty = true;
    }
    if (next_ghost_count != ghost_to_count) {
        ghost_from_count = ghost_to_count;
        ghost_to_count = next_ghost_count;
        ghost_transition_started_ms = now_ms;
        last_frame_ms = 0U;
    }
    if (state == current_state) {
        if (balance_changed) {
            last_frame_ms = 0U;
        }
        return;
    }
    current_state = state;
    if (!running_family_change) {
        state_started_ms = now_ms;
    }
    last_frame_ms = 0U;
    if (!running_family_change) {
        pager_blossom_motion_set_target(&blossom_motion, state, now_ms);
    }
}

void pager_display_ui_update(uint32_t now_ms) {
    if (!initialized) {
        return;
    }
    if (last_frame_ms == 0U ||
        (uint32_t)(now_ms - last_frame_ms) >= PAGER_SCENE_FRAME_MS) {
        render_frame(now_ms);
        last_frame_ms = now_ms;
    }
}
