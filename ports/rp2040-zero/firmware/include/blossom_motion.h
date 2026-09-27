#ifndef CODEX_BLOSSOM_MOTION_H
#define CODEX_BLOSSOM_MOTION_H

#include "blossom_asset.h"
#include "pager_core.h"

#include <stdbool.h>
#include <stdint.h>

#define PAGER_READY_TO_RUNNING_MS 800U
#define PAGER_RUNNING_TO_READY_MS 1200U
#define PAGER_OFFLINE_TO_READY_MS 1200U

#define PAGER_BLOSSOM_OFFLINE_COLOR 0x8410U
#define PAGER_BLOSSOM_READY_COLOR 0x3E93U
#define PAGER_BLOSSOM_RUNNING_COLOR 0x625CU
#define PAGER_BLOSSOM_WAIT_COLOR 0xFD43U

typedef struct {
    int32_t center_x_q8;
    int32_t center_y_q8;
    int16_t angle_q8;
    uint16_t scale_q12;
    uint16_t color;
    uint8_t opacity;
} pager_blossom_piece_pose_t;

typedef struct {
    pager_blossom_piece_pose_t pieces[BLOSSOM_PIECE_COUNT];
    uint8_t balance_opacity;
    uint8_t petal_layer_opacity;
    uint8_t full_layer_opacity;
    uint16_t full_layer_color;
    int16_t composite_angle_q8;
    int16_t angular_velocity_q8;
    bool ordered_orbit;
} pager_blossom_model_t;

typedef struct {
    pager_state_t source;
    pager_state_t target;
    uint32_t started_ms;
    pager_blossom_model_t start;
    pager_blossom_model_t current;
} pager_blossom_motion_t;

void pager_blossom_motion_init(
    pager_blossom_motion_t *motion,
    pager_state_t state,
    uint32_t now_ms);
void pager_blossom_motion_set_target(
    pager_blossom_motion_t *motion,
    pager_state_t target,
    uint32_t now_ms);
void pager_blossom_motion_sample(
    pager_blossom_motion_t *motion,
    uint32_t now_ms,
    pager_blossom_model_t *model);

#endif
