#ifndef CODEX_DISPLAY_SCENE_H
#define CODEX_DISPLAY_SCENE_H

#include "blossom_motion.h"
#include "pager_core.h"

#include <stdbool.h>
#include <stdint.h>

#define PAGER_SCENE_CENTER_X 120
#define PAGER_SCENE_CENTER_Y 120
#define PAGER_SCENE_REGION_X 6
#define PAGER_SCENE_REGION_Y 6
#define PAGER_SCENE_REGION_SIZE 228U
#define PAGER_SCENE_TILE_SIZE 12U
#define PAGER_SCENE_TILE_COUNT \
    (PAGER_SCENE_REGION_SIZE / PAGER_SCENE_TILE_SIZE)
#define PAGER_SCENE_FRAME_MS 16U
#define PAGER_SCENE_TRANSITION_MS 650U
#define PAGER_MULTI_GHOST_MAX 3U
#define PAGER_MULTI_GHOST_FADE_MS 320U

typedef struct {
    uint8_t angle;
    uint16_t scale_q12;
    uint8_t opacity;
    uint8_t ring_radius;
} pager_scene_pose_t;

typedef struct {
    bool visible;
    int16_t value_center_x;
    int16_t value_left;
    int16_t value_right;
} pager_idle_layout_t;

typedef struct {
    int16_t left;
    int16_t top;
    int16_t right;
    int16_t bottom;
} pager_scene_piece_clip_t;

typedef struct {
    uint32_t rows[PAGER_SCENE_TILE_COUNT];
} pager_scene_tile_map_t;

typedef struct {
    const uint8_t *mask_4bpp;
    uint16_t mask_size;
    int16_t sin_q15;
    int16_t cos_q15;
    int32_t factor_q16;
    uint16_t color;
    uint8_t opacity;
    int16_t center_x;
    int16_t center_y;
} pager_scene_prepared_layer_t;

typedef struct {
    pager_scene_prepared_layer_t pieces[BLOSSOM_PIECE_COUNT];
    pager_scene_prepared_layer_t full;
    pager_scene_prepared_layer_t ghosts[PAGER_MULTI_GHOST_MAX];
    char value_text[5];
    uint8_t value_length;
    uint8_t balance_opacity;
    int16_t value_left;
    int16_t value_top;
    uint8_t ghost_count;
    bool petals_visible;
    bool full_visible;
} pager_scene_render_context_t;

uint16_t pager_scene_rgb565(uint8_t red, uint8_t green, uint8_t blue);
uint16_t pager_scene_base_color(pager_state_t state);
uint16_t pager_scene_logo_color(pager_state_t state);
uint16_t pager_scene_ring_color(pager_state_t state);
uint16_t pager_scene_hex_color(void);
uint16_t pager_scene_background_color(
    pager_state_t state,
    uint32_t elapsed_ms,
    int16_t x,
    int16_t y);
bool pager_scene_is_hex_outline(int16_t x, int16_t y);
pager_scene_pose_t pager_scene_pose(pager_state_t state, uint32_t elapsed_ms);
uint8_t pager_scene_transition_alpha(uint32_t elapsed_ms);
uint8_t pager_scene_ghost_count(
    pager_state_t state, uint32_t running_count);
void pager_scene_ghost_opacity(
    uint8_t from_count,
    uint8_t to_count,
    uint32_t elapsed_ms,
    uint8_t output[PAGER_MULTI_GHOST_MAX]);
uint8_t pager_scene_sample_logo(
    int16_t x,
    int16_t y,
    uint8_t angle,
    uint16_t scale_q12);
uint8_t pager_scene_sample_piece_logo(
    int16_t x,
    int16_t y,
    uint8_t angle,
    uint16_t scale_q12,
    uint8_t piece);
pager_idle_layout_t pager_scene_idle_layout(const char *balance);
void pager_scene_prepare_motion(
    const pager_blossom_model_t *model,
    pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT]);
void pager_scene_tile_map_clear(pager_scene_tile_map_t *map);
void pager_scene_tile_map_fill(pager_scene_tile_map_t *map);
void pager_scene_mark_balance_tiles(pager_scene_tile_map_t *map);
bool pager_scene_tile_dirty(
    const pager_scene_tile_map_t *map, uint8_t tile_x, uint8_t tile_y);
void pager_scene_mark_motion_tiles(
    const pager_blossom_model_t *previous,
    const pager_scene_piece_clip_t previous_clips[BLOSSOM_PIECE_COUNT],
    const pager_blossom_model_t *current,
    const pager_scene_piece_clip_t current_clips[BLOSSOM_PIECE_COUNT],
    pager_scene_tile_map_t *map);
uint8_t pager_scene_tile_layer_mask(
    const pager_blossom_model_t *model,
    const pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT],
    uint8_t tile_x,
    uint8_t tile_y);
bool pager_scene_tile_full_layer_active(
    const pager_blossom_model_t *model, uint8_t tile_x, uint8_t tile_y);
void pager_scene_prepare_render_context(
    const pager_blossom_model_t *model,
    const char *balance,
    uint8_t ghost_count,
    const uint8_t ghost_opacity[PAGER_MULTI_GHOST_MAX],
    uint32_t motion_ms,
    pager_scene_render_context_t *context);
void pager_scene_render_prepared_span(
    pager_state_t state,
    uint32_t elapsed_ms,
    const pager_scene_render_context_t *context,
    uint8_t active_piece_mask,
    bool full_layer_active,
    int16_t x_start,
    int16_t y,
    uint16_t pixel_count,
    uint16_t *pixels);
void pager_scene_render_motion_span(
    pager_state_t state,
    uint32_t elapsed_ms,
    const pager_blossom_model_t *model,
    uint8_t active_piece_mask,
    bool full_layer_active,
    const char *balance,
    int16_t x_start,
    int16_t y,
    uint16_t pixel_count,
    uint16_t *pixels);
void pager_scene_render_motion_row(
    pager_state_t state,
    uint32_t elapsed_ms,
    const pager_blossom_model_t *model,
    const pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT],
    const char *balance,
    int16_t y,
    uint16_t *pixels);
void pager_scene_render_row(
    pager_state_t state,
    uint32_t elapsed_ms,
    const char *balance,
    int16_t y,
    uint16_t *pixels);

#endif
