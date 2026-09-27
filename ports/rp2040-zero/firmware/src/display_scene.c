#include "display_scene.h"

#include "blossom_asset.h"
#include "tiny_font.h"

#include <stddef.h>
#include <string.h>

#define IDLE_LOGO_CENTER_Y 90
#define IDLE_WEEK_TOP 139
#define IDLE_WEEK_SCALE 2U
#define IDLE_VALUE_TOP 161
#define IDLE_VALUE_SCALE 4U

static const uint16_t g_ghost_period_ms[PAGER_MULTI_GHOST_MAX] = {
    5600U, 4800U, 6400U};
static const uint16_t g_ghost_scale_ratio_q12[PAGER_MULTI_GHOST_MAX] = {
    4424U, 4751U, 5079U};
static const uint8_t g_ghost_base_opacity[PAGER_MULTI_GHOST_MAX] = {
    77U, 59U, 43U};

typedef pager_scene_prepared_layer_t logo_layer_t;

typedef struct {
    const logo_layer_t *layer;
    int32_t source_x_q8;
    int32_t source_y_q8;
    int32_t step_x_q8;
    int32_t step_y_q8;
} logo_sampler_t;

static int16_t sin_q15_interpolated(uint16_t angle_q8) {
    const uint8_t index = (uint8_t)(angle_q8 >> 8U);
    const uint8_t fraction = (uint8_t)angle_q8;
    const int32_t from = g_sin_q15[index];
    const int32_t to = g_sin_q15[(uint8_t)(index + 1U)];

    return (int16_t)(
        from + ((to - from) * fraction + 128) / 256);
}

uint16_t pager_scene_rgb565(uint8_t red, uint8_t green, uint8_t blue) {
    return (uint16_t)((((uint16_t)red & 0xF8U) << 8U) |
                      (((uint16_t)green & 0xFCU) << 3U) |
                      ((uint16_t)blue >> 3U));
}

uint16_t pager_scene_base_color(pager_state_t state) {
    (void)state;
    return pager_scene_rgb565(8U, 12U, 32U);
}

static uint16_t accent_color(pager_state_t state) {
    switch (state) {
        case PAGER_RUNNING: return pager_scene_rgb565(56U, 72U, 255U);
        case PAGER_MULTI: return pager_scene_rgb565(126U, 48U, 255U);
        case PAGER_WAIT: return pager_scene_rgb565(230U, 115U, 20U);
        case PAGER_DONE: return pager_scene_rgb565(28U, 190U, 150U);
        case PAGER_ERROR: return pager_scene_rgb565(220U, 65U, 75U);
        case PAGER_OFFLINE: return pager_scene_rgb565(145U, 75U, 85U);
        default: return pager_scene_rgb565(92U, 88U, 125U);
    }
}

uint16_t pager_scene_logo_color(pager_state_t state) {
    switch (state) {
        case PAGER_RUNNING: return pager_scene_rgb565(208U, 24U, 255U);
        case PAGER_MULTI: return pager_scene_rgb565(224U, 64U, 255U);
        case PAGER_WAIT: return pager_scene_rgb565(255U, 164U, 38U);
        case PAGER_DONE: return pager_scene_rgb565(218U, 255U, 246U);
        case PAGER_ERROR: return pager_scene_rgb565(255U, 110U, 120U);
        case PAGER_OFFLINE: return pager_scene_rgb565(190U, 120U, 130U);
        default: return pager_scene_rgb565(126U, 129U, 145U);
    }
}

uint16_t pager_scene_ring_color(pager_state_t state) {
    switch (state) {
        case PAGER_RUNNING: return pager_scene_rgb565(24U, 64U, 255U);
        case PAGER_MULTI: return pager_scene_rgb565(72U, 72U, 255U);
        case PAGER_WAIT: return pager_scene_rgb565(255U, 151U, 25U);
        case PAGER_DONE: return pager_scene_rgb565(40U, 226U, 178U);
        case PAGER_ERROR: return pager_scene_rgb565(235U, 80U, 90U);
        case PAGER_OFFLINE: return pager_scene_rgb565(165U, 85U, 95U);
        default: return pager_scene_rgb565(92U, 94U, 112U);
    }
}

uint16_t pager_scene_hex_color(void) {
    return pager_scene_rgb565(222U, 228U, 244U);
}

bool pager_scene_is_hex_outline(int16_t x, int16_t y) {
    int16_t half_width;
    int16_t left;
    int16_t right;

    if (x < 0 || x >= 240 || y < 0 || y >= 240) {
        return false;
    }
    if (y <= 60) {
        half_width = (int16_t)((104 * y + 30) / 60);
    } else if (y < 180) {
        half_width = 104;
    } else {
        half_width = (int16_t)((104 * (239 - y) + 29) / 59);
    }
    left = (int16_t)(120 - half_width);
    right = (int16_t)(120 + half_width);
    return (x >= left - 1 && x <= left + 1) ||
           (x >= right - 1 && x <= right + 1);
}

static uint16_t blend565(uint16_t background, uint16_t foreground, uint8_t alpha) {
    const uint8_t inverse = (uint8_t)(15U - alpha);
    const uint16_t red = (uint16_t)((((background >> 11U) & 0x1FU) * inverse +
        ((foreground >> 11U) & 0x1FU) * alpha + 7U) / 15U);
    const uint16_t green = (uint16_t)((((background >> 5U) & 0x3FU) * inverse +
        ((foreground >> 5U) & 0x3FU) * alpha + 7U) / 15U);
    const uint16_t blue = (uint16_t)(((background & 0x1FU) * inverse +
        (foreground & 0x1FU) * alpha + 7U) / 15U);
    return (uint16_t)((red << 11U) | (green << 5U) | blue);
}

static uint16_t lerp_u16(
    uint16_t from, uint16_t to, uint32_t elapsed, uint32_t duration) {
    if (elapsed >= duration) {
        return to;
    }
    return (uint16_t)(from + ((int32_t)to - from) * (int32_t)elapsed /
                                 (int32_t)duration);
}

uint8_t pager_scene_transition_alpha(uint32_t elapsed_ms) {
    uint32_t time_q15;
    uint32_t smooth_q15;

    if (elapsed_ms >= PAGER_SCENE_TRANSITION_MS) {
        return 255U;
    }
    time_q15 = (elapsed_ms << 15U) / PAGER_SCENE_TRANSITION_MS;
    smooth_q15 = (uint32_t)(((uint64_t)time_q15 * time_q15 *
        (3U * 32768U - 2U * time_q15)) >> 30U);
    return (uint8_t)((smooth_q15 * 255U + 16384U) >> 15U);
}

uint8_t pager_scene_ghost_count(
    pager_state_t state, uint32_t running_count) {
    uint32_t additional;

    if (state != PAGER_MULTI || running_count < 2U) {
        return 0U;
    }
    additional = running_count - 1U;
    return (uint8_t)(additional > PAGER_MULTI_GHOST_MAX
        ? PAGER_MULTI_GHOST_MAX
        : additional);
}

void pager_scene_ghost_opacity(
    uint8_t from_count,
    uint8_t to_count,
    uint32_t elapsed_ms,
    uint8_t output[PAGER_MULTI_GHOST_MAX]) {
    const uint32_t time_q15 = elapsed_ms >= PAGER_MULTI_GHOST_FADE_MS
        ? 32768U
        : (elapsed_ms << 15U) / PAGER_MULTI_GHOST_FADE_MS;
    const uint32_t smooth_q15 = (uint32_t)(((uint64_t)time_q15 * time_q15 *
        (3U * 32768U - 2U * time_q15)) >> 30U);
    uint8_t index;

    if (output == NULL) {
        return;
    }
    for (index = 0U; index < PAGER_MULTI_GHOST_MAX; ++index) {
        const bool was_visible = index < from_count;
        const bool is_visible = index < to_count;
        const uint8_t alpha = (uint8_t)(
            (smooth_q15 * 255U + 16384U) >> 15U);

        output[index] = was_visible == is_visible
            ? (was_visible ? 255U : 0U)
            : (is_visible ? alpha : (uint8_t)(255U - alpha));
    }
}

pager_scene_pose_t pager_scene_pose(pager_state_t state, uint32_t elapsed_ms) {
    pager_scene_pose_t pose = {0U, 3604U, 255U, 85U};

    if (state == PAGER_RUNNING || state == PAGER_MULTI) {
        const uint32_t cycle = state == PAGER_MULTI ? 4600U : 4700U;
        const uint8_t phase = (uint8_t)(((elapsed_ms % cycle) * 256U) / cycle);
        const int16_t cosine = g_sin_q15[(uint8_t)(phase + 64U)];
        pose.angle = (uint8_t)(phase * 2U -
            ((int32_t)g_sin_q15[phase] * 13 >> 15U) -
            ((int32_t)g_sin_q15[(uint8_t)(phase * 2U)] * 4 >> 15U));
        pose.scale_q12 = state == PAGER_MULTI
            ? (uint16_t)(3523U + ((int32_t)(32767 - cosine) * 1229) / 65534)
            : (uint16_t)(3359U + ((int32_t)(32767 - cosine) * 1720) / 65534);
    } else if (state == PAGER_WAIT) {
        const uint8_t phase =
            (uint8_t)(((elapsed_ms % 1500U) * 256U) / 1500U);
        pose.scale_q12 = (uint16_t)(3768 +
            ((int32_t)g_sin_q15[phase] * 150 >> 15U));
        pose.ring_radius = (uint8_t)(85 +
            ((int32_t)g_sin_q15[phase] * 3 >> 15U));
    } else if (state == PAGER_DONE) {
        const uint32_t pulse = elapsed_ms % 3000U;
        if (pulse < 180U) {
            pose.scale_q12 = lerp_u16(3604U, 3441U, pulse, 180U);
        } else if (pulse < 390U) {
            pose.scale_q12 = lerp_u16(3441U, 3932U, pulse - 180U, 210U);
        } else if (pulse < 600U) {
            pose.scale_q12 = lerp_u16(3932U, 3604U, pulse - 390U, 210U);
        }
        if (pulse < 390U) {
            pose.ring_radius = (uint8_t)(85U + pulse * 6U / 390U);
        } else if (pulse < 600U) {
            pose.ring_radius =
                (uint8_t)(91U - (pulse - 390U) * 6U / 210U);
        }
    } else if (state == PAGER_IDLE) {
        pose.scale_q12 = 3195U;
    }
    return pose;
}

static uint8_t layer_mask_value(
    const logo_layer_t *layer, int16_t x, int16_t y) {
    uint32_t index;
    uint8_t packed;

    if (layer == NULL || layer->mask_4bpp == NULL ||
        x < 0 || y < 0 || x >= (int16_t)layer->mask_size ||
        y >= (int16_t)layer->mask_size) {
        return 0U;
    }
    index = (uint32_t)y * layer->mask_size + (uint16_t)x;
    packed = layer->mask_4bpp[index >> 1U];
    return (index & 1U) != 0U ? (packed & 0x0FU) : (packed >> 4U);
}

static logo_layer_t make_mask_layer_at(
    int16_t angle_q8,
    uint16_t scale_q12,
    uint16_t color,
    uint8_t opacity,
    int16_t center_x,
    int16_t center_y,
    const uint8_t *mask_4bpp,
    uint16_t mask_size,
    uint16_t nominal_output_size) {
    logo_layer_t layer;
    const uint32_t denominator =
        (uint32_t)nominal_output_size * scale_q12;

    layer.mask_4bpp = mask_4bpp;
    layer.mask_size = mask_size;
    layer.sin_q15 = sin_q15_interpolated((uint16_t)angle_q8);
    layer.cos_q15 = sin_q15_interpolated(
        (uint16_t)((uint16_t)angle_q8 + 64U * 256U));
    layer.factor_q16 =
        (int32_t)(((uint64_t)mask_size << 28U) / denominator);
    layer.color = color;
    layer.opacity = opacity;
    layer.center_x = center_x;
    layer.center_y = center_y;
    return layer;
}

static logo_layer_t make_layer(
    uint8_t angle, uint16_t scale_q12, uint16_t color, uint8_t opacity) {
    return make_mask_layer_at(
        (int16_t)((uint16_t)angle << 8U),
        scale_q12,
        color,
        opacity,
        PAGER_SCENE_CENTER_X,
        PAGER_SCENE_CENTER_Y,
        g_blossom_alpha_4bpp,
        BLOSSOM_MASK_SIZE,
        132U);
}

static logo_layer_t make_layer_at(
    int16_t angle_q8,
    uint16_t scale_q12,
    uint16_t color,
    uint8_t opacity,
    int16_t center_x,
    int16_t center_y) {
    return make_mask_layer_at(
        angle_q8,
        scale_q12,
        color,
        opacity,
        center_x,
        center_y,
        g_blossom_alpha_4bpp,
        BLOSSOM_MASK_SIZE,
        132U);
}

static logo_sampler_t init_sampler(
    const logo_layer_t *layer, int16_t x, int16_t y) {
    logo_sampler_t sampler;
    const int32_t dx_q8 =
        ((int32_t)x << 8U) + 128 - ((int32_t)layer->center_x << 8U);
    const int32_t dy_q8 =
        ((int32_t)y << 8U) + 128 - ((int32_t)layer->center_y << 8U);
    const int64_t rotated_x =
        (int64_t)dx_q8 * layer->cos_q15 + (int64_t)dy_q8 * layer->sin_q15;
    const int64_t rotated_y =
        -(int64_t)dx_q8 * layer->sin_q15 + (int64_t)dy_q8 * layer->cos_q15;
    sampler.layer = layer;
    sampler.source_x_q8 =
        (int32_t)((rotated_x * layer->factor_q16) >> 31U) +
        (int32_t)(layer->mask_size - 1U) * 128;
    sampler.source_y_q8 =
        (int32_t)((rotated_y * layer->factor_q16) >> 31U) +
        (int32_t)(layer->mask_size - 1U) * 128;
    sampler.step_x_q8 = (int32_t)(((int64_t)256 * layer->cos_q15 *
        layer->factor_q16) >> 31U);
    sampler.step_y_q8 = (int32_t)((-(int64_t)256 * layer->sin_q15 *
        layer->factor_q16) >> 31U);
    return sampler;
}

static logo_sampler_t init_span_sampler(
    const logo_layer_t *layer, int16_t x, int16_t y) {
    logo_sampler_t sampler =
        init_sampler(layer, PAGER_SCENE_REGION_X, y);
    const int32_t offset = x - PAGER_SCENE_REGION_X;

    sampler.source_x_q8 += offset * sampler.step_x_q8;
    sampler.source_y_q8 += offset * sampler.step_y_q8;
    return sampler;
}

static uint8_t sampler_alpha(logo_sampler_t *sampler) {
    uint8_t alpha = layer_mask_value(
        sampler->layer,
        (int16_t)((sampler->source_x_q8 + 128) >> 8U),
        (int16_t)((sampler->source_y_q8 + 128) >> 8U));
    sampler->source_x_q8 += sampler->step_x_q8;
    sampler->source_y_q8 += sampler->step_y_q8;
    if (sampler->layer->opacity != 255U) {
        alpha = (uint8_t)(((uint16_t)alpha * sampler->layer->opacity + 127U) /
                          255U);
    }
    return alpha;
}

static void sampler_skip(logo_sampler_t *sampler) {
    sampler->source_x_q8 += sampler->step_x_q8;
    sampler->source_y_q8 += sampler->step_y_q8;
}

uint8_t pager_scene_sample_logo(
    int16_t x, int16_t y, uint8_t angle, uint16_t scale_q12) {
    logo_layer_t layer = make_layer(angle, scale_q12, 0U, 255U);
    logo_sampler_t sampler = init_sampler(&layer, x, y);
    return sampler_alpha(&sampler);
}

uint8_t pager_scene_sample_piece_logo(
    int16_t x,
    int16_t y,
    uint8_t angle,
    uint16_t scale_q12,
    uint8_t piece) {
    logo_layer_t layer = make_layer(angle, scale_q12, 0U, 255U);
    logo_sampler_t sampler = init_sampler(&layer, x, y);

    if (piece >= BLOSSOM_PIECE_COUNT) {
        return 0U;
    }
    layer.mask_4bpp = g_blossom_piece_alpha_4bpp[piece];
    sampler.layer = &layer;
    return sampler_alpha(&sampler);
}

static uint16_t text_width(size_t length, uint8_t scale) {
    if (length == 0U) {
        return 0U;
    }
    return (uint16_t)(((length * (TINY_FONT_WIDTH + 1U)) - 1U) * scale);
}

static size_t format_balance(const char *balance, char output[5]) {
    size_t length = 0U;
    uint16_t value = 0U;

    if (balance == NULL || balance[0] == '\0') {
        return 0U;
    }
    while (balance[length] != '\0') {
        if (length >= 3U || balance[length] < '0' || balance[length] > '9') {
            return 0U;
        }
        value = (uint16_t)(value * 10U + (uint16_t)(balance[length] - '0'));
        ++length;
    }
    if (length == 0U || value > 100U ||
        (length > 1U && balance[0] == '0')) {
        return 0U;
    }
    for (value = 0U; value < length; ++value) {
        output[value] = balance[value];
    }
    output[length] = '\0';
    return length;
}

pager_idle_layout_t pager_scene_idle_layout(const char *balance) {
    pager_idle_layout_t layout = {
        false,
        PAGER_SCENE_CENTER_X,
        PAGER_SCENE_CENTER_X,
        PAGER_SCENE_CENTER_X,
    };
    char value_text[5];
    const size_t length = format_balance(balance, value_text);
    uint16_t width;

    if (length == 0U) {
        return layout;
    }
    width = text_width(length, IDLE_VALUE_SCALE);
    layout.visible = true;
    layout.value_left =
        (int16_t)(PAGER_SCENE_CENTER_X - (int16_t)(width / 2U));
    layout.value_right = (int16_t)(layout.value_left + (int16_t)width - 1);
    return layout;
}

static bool sample_text(
    const char *text,
    size_t length,
    int16_t left,
    int16_t top,
    uint8_t scale,
    int16_t x,
    int16_t y) {
    const int16_t local_x = (int16_t)(x - left);
    const int16_t local_y = (int16_t)(y - top);
    const uint16_t stride = (uint16_t)((TINY_FONT_WIDTH + 1U) * scale);
    size_t glyph_index;
    uint16_t glyph_x;

    if (local_x < 0 || local_y < 0 ||
        local_y >= (int16_t)(TINY_FONT_HEIGHT * scale)) {
        return false;
    }
    glyph_index = (size_t)((uint16_t)local_x / stride);
    if (glyph_index >= length) {
        return false;
    }
    glyph_x = (uint16_t)local_x % stride;
    if (glyph_x >= TINY_FONT_WIDTH * scale) {
        return false;
    }
    return tiny_font_sample(
        text[glyph_index],
        (uint8_t)(glyph_x / scale),
        (uint8_t)((uint16_t)local_y / scale));
}

uint16_t pager_scene_background_color(
    pager_state_t state, uint32_t elapsed_ms, int16_t x, int16_t y) {
    const uint8_t phase = (uint8_t)(elapsed_ms / 35U);
    const int16_t ambient_x = (int16_t)(PAGER_SCENE_CENTER_X +
        ((int32_t)g_sin_q15[(uint8_t)(phase + 64U)] * 10 >> 15U));
    const int16_t ambient_y = (int16_t)(PAGER_SCENE_CENTER_Y +
        ((int32_t)g_sin_q15[phase] * 12 >> 15U));
    const int32_t dx = x - ambient_x;
    const int32_t dy = y - ambient_y;
    const int32_t distance2 = dx * dx + dy * dy;
    const int32_t radius2 = 72 * 72;
    const uint8_t maximum = state == PAGER_MULTI ? 8U
        : (state == PAGER_RUNNING ? 7U : 4U);
    const uint32_t intensity = distance2 < radius2
        ? (uint32_t)(radius2 - distance2) * maximum : 0U;
    const uint8_t alpha =
        (uint8_t)((intensity * 202U + (1U << 19U)) >> 20U);

    return blend565(pager_scene_base_color(state), accent_color(state), alpha);
}

void pager_scene_prepare_motion(
    const pager_blossom_model_t *model,
    pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT]) {
    uint8_t piece;

    if (model == NULL || clips == NULL) {
        return;
    }
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        const pager_blossom_piece_pose_t *pose = &model->pieces[piece];
        const uint16_t angle_q8 = (uint16_t)pose->angle_q8;
        const int32_t sine = sin_q15_interpolated(angle_q8);
        const int32_t cosine = sin_q15_interpolated(
            (uint16_t)(angle_q8 + 64U * 256U));
        const int32_t scale_q16 = (int32_t)(132U * pose->scale_q12 / 8U);
        const int32_t source_center_x_q8 =
            ((int32_t)g_blossom_piece_min_x[piece] +
             g_blossom_piece_max_x[piece]) * 128;
        const int32_t source_center_y_q8 =
            ((int32_t)g_blossom_piece_min_y[piece] +
             g_blossom_piece_max_y[piece]) * 128;
        const int32_t half_width_q8 =
            ((int32_t)g_blossom_piece_max_x[piece] -
             g_blossom_piece_min_x[piece] + 1) * 128;
        const int32_t half_height_q8 =
            ((int32_t)g_blossom_piece_max_y[piece] -
             g_blossom_piece_min_y[piece] + 1) * 128;
        const int32_t source_offset_x_q8 =
            source_center_x_q8 +
            128 - (int32_t)(BLOSSOM_MASK_SIZE - 1U) * 128;
        const int32_t source_offset_y_q8 =
            source_center_y_q8 +
            128 - (int32_t)(BLOSSOM_MASK_SIZE - 1U) * 128;
        const int32_t offset_x_q8 = (int32_t)(
            (((int64_t)source_offset_x_q8 * cosine -
              (int64_t)source_offset_y_q8 * sine) *
             scale_q16) >> 31U);
        const int32_t offset_y_q8 = (int32_t)(
            (((int64_t)source_offset_x_q8 * sine +
              (int64_t)source_offset_y_q8 * cosine) *
             scale_q16) >> 31U);
        const int16_t center_x = (int16_t)(
            (pose->center_x_q8 + offset_x_q8 + 128) >> 8U);
        const int16_t center_y = (int16_t)(
            (pose->center_y_q8 + offset_y_q8 + 128) >> 8U);
        const int16_t extent_x = (int16_t)(
            (((int64_t)(cosine < 0 ? -cosine : cosine) * half_width_q8 +
              (int64_t)(sine < 0 ? -sine : sine) * half_height_q8) *
              scale_q16 + ((int64_t)1 << 39U) - 1) >> 39U);
        const int16_t extent_y = (int16_t)(
            (((int64_t)(sine < 0 ? -sine : sine) * half_width_q8 +
              (int64_t)(cosine < 0 ? -cosine : cosine) * half_height_q8) *
              scale_q16 + ((int64_t)1 << 39U) - 1) >> 39U);
        int16_t left = (int16_t)(center_x - extent_x - 2);
        int16_t top = (int16_t)(center_y - extent_y - 2);
        int16_t right = (int16_t)(center_x + extent_x + 2);
        int16_t bottom = (int16_t)(center_y + extent_y + 2);

        if (left < PAGER_SCENE_REGION_X) {
            left = PAGER_SCENE_REGION_X;
        }
        if (top < PAGER_SCENE_REGION_Y) {
            top = PAGER_SCENE_REGION_Y;
        }
        if (right >= PAGER_SCENE_REGION_X + (int16_t)PAGER_SCENE_REGION_SIZE) {
            right = PAGER_SCENE_REGION_X +
                (int16_t)PAGER_SCENE_REGION_SIZE - 1;
        }
        if (bottom >= PAGER_SCENE_REGION_Y + (int16_t)PAGER_SCENE_REGION_SIZE) {
            bottom = PAGER_SCENE_REGION_Y +
                (int16_t)PAGER_SCENE_REGION_SIZE - 1;
        }
        clips[piece].left = left;
        clips[piece].top = top;
        clips[piece].right = right;
        clips[piece].bottom = bottom;
    }
}

static bool rectangles_intersect(
    int16_t left,
    int16_t top,
    int16_t right,
    int16_t bottom,
    const pager_scene_piece_clip_t *clip) {
    return clip != NULL &&
           left <= clip->right &&
           right >= clip->left &&
           top <= clip->bottom &&
           bottom >= clip->top;
}

static pager_scene_piece_clip_t full_layer_clip(
    const pager_blossom_model_t *model) {
    pager_scene_piece_clip_t clip = {
        PAGER_SCENE_CENTER_X,
        PAGER_SCENE_CENTER_Y,
        PAGER_SCENE_CENTER_X,
        PAGER_SCENE_CENTER_Y,
    };

    if (model != NULL) {
        const uint32_t scale_q12 = model->pieces[0].scale_q12;
        const int16_t extent = (int16_t)(
            ((uint32_t)132U * scale_q12 + 8191U) / 8192U + 3U);

        clip.left = (int16_t)(PAGER_SCENE_CENTER_X - extent);
        clip.top = (int16_t)(PAGER_SCENE_CENTER_Y - extent);
        clip.right = (int16_t)(PAGER_SCENE_CENTER_X + extent);
        clip.bottom = (int16_t)(PAGER_SCENE_CENTER_Y + extent);
    }
    return clip;
}

void pager_scene_tile_map_clear(pager_scene_tile_map_t *map) {
    uint8_t row;

    if (map == NULL) {
        return;
    }
    for (row = 0U; row < PAGER_SCENE_TILE_COUNT; ++row) {
        map->rows[row] = 0U;
    }
}

void pager_scene_tile_map_fill(pager_scene_tile_map_t *map) {
    const uint32_t row_bits =
        ((uint32_t)1U << PAGER_SCENE_TILE_COUNT) - 1U;
    uint8_t row;

    if (map == NULL) {
        return;
    }
    for (row = 0U; row < PAGER_SCENE_TILE_COUNT; ++row) {
        map->rows[row] = row_bits;
    }
}

bool pager_scene_tile_dirty(
    const pager_scene_tile_map_t *map, uint8_t tile_x, uint8_t tile_y) {
    return map != NULL &&
           tile_x < PAGER_SCENE_TILE_COUNT &&
           tile_y < PAGER_SCENE_TILE_COUNT &&
           (map->rows[tile_y] & ((uint32_t)1U << tile_x)) != 0U;
}

static void mark_clip_tiles(
    pager_scene_tile_map_t *map, const pager_scene_piece_clip_t *clip) {
    int16_t local_left;
    int16_t local_top;
    int16_t local_right;
    int16_t local_bottom;
    uint8_t tile_top;
    uint8_t tile_bottom;
    uint8_t tile_left;
    uint8_t tile_right;
    uint8_t tile_y;

    if (map == NULL || clip == NULL) {
        return;
    }
    local_left = (int16_t)(clip->left - PAGER_SCENE_REGION_X);
    local_top = (int16_t)(clip->top - PAGER_SCENE_REGION_Y);
    local_right = (int16_t)(clip->right - PAGER_SCENE_REGION_X);
    local_bottom = (int16_t)(clip->bottom - PAGER_SCENE_REGION_Y);
    if (local_right < 0 || local_bottom < 0 ||
        local_left >= (int16_t)PAGER_SCENE_REGION_SIZE ||
        local_top >= (int16_t)PAGER_SCENE_REGION_SIZE) {
        return;
    }
    if (local_left < 0) {
        local_left = 0;
    }
    if (local_top < 0) {
        local_top = 0;
    }
    if (local_right >= (int16_t)PAGER_SCENE_REGION_SIZE) {
        local_right = (int16_t)PAGER_SCENE_REGION_SIZE - 1;
    }
    if (local_bottom >= (int16_t)PAGER_SCENE_REGION_SIZE) {
        local_bottom = (int16_t)PAGER_SCENE_REGION_SIZE - 1;
    }
    tile_left = (uint8_t)(local_left / PAGER_SCENE_TILE_SIZE);
    tile_top = (uint8_t)(local_top / PAGER_SCENE_TILE_SIZE);
    tile_right = (uint8_t)(local_right / PAGER_SCENE_TILE_SIZE);
    tile_bottom = (uint8_t)(local_bottom / PAGER_SCENE_TILE_SIZE);
    for (tile_y = tile_top; tile_y <= tile_bottom; ++tile_y) {
        const uint32_t width = (uint32_t)(tile_right - tile_left + 1U);
        const uint32_t bits =
            (((uint32_t)1U << width) - 1U) << tile_left;

        map->rows[tile_y] |= bits;
    }
}

void pager_scene_mark_balance_tiles(pager_scene_tile_map_t *map) {
    const pager_scene_piece_clip_t balance_clip = {
        PAGER_SCENE_CENTER_X - 26,
        PAGER_SCENE_CENTER_Y - 16,
        PAGER_SCENE_CENTER_X + 26,
        PAGER_SCENE_CENTER_Y + 16,
    };

    mark_clip_tiles(map, &balance_clip);
}

static void mark_model_tiles(
    const pager_blossom_model_t *model,
    const pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT],
    pager_scene_tile_map_t *map) {
    uint8_t piece;

    if (model == NULL || map == NULL) {
        return;
    }
    if (model->petal_layer_opacity != 0U && clips != NULL) {
        for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
            if (model->pieces[piece].opacity != 0U) {
                mark_clip_tiles(map, &clips[piece]);
            }
        }
    }
    if (model->full_layer_opacity != 0U &&
        model->pieces[0].opacity != 0U) {
        const pager_scene_piece_clip_t clip = full_layer_clip(model);

        mark_clip_tiles(map, &clip);
    }
}

void pager_scene_mark_motion_tiles(
    const pager_blossom_model_t *previous,
    const pager_scene_piece_clip_t previous_clips[BLOSSOM_PIECE_COUNT],
    const pager_blossom_model_t *current,
    const pager_scene_piece_clip_t current_clips[BLOSSOM_PIECE_COUNT],
    pager_scene_tile_map_t *map) {
    pager_scene_tile_map_clear(map);
    mark_model_tiles(previous, previous_clips, map);
    mark_model_tiles(current, current_clips, map);
    if (previous != NULL && current != NULL &&
        previous->balance_opacity != current->balance_opacity) {
        pager_scene_mark_balance_tiles(map);
    }
}

uint8_t pager_scene_tile_layer_mask(
    const pager_blossom_model_t *model,
    const pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT],
    uint8_t tile_x,
    uint8_t tile_y) {
    const int16_t left = (int16_t)(
        PAGER_SCENE_REGION_X + tile_x * PAGER_SCENE_TILE_SIZE);
    const int16_t top = (int16_t)(
        PAGER_SCENE_REGION_Y + tile_y * PAGER_SCENE_TILE_SIZE);
    const int16_t right =
        (int16_t)(left + PAGER_SCENE_TILE_SIZE - 1U);
    const int16_t bottom =
        (int16_t)(top + PAGER_SCENE_TILE_SIZE - 1U);
    uint8_t mask = 0U;
    uint8_t piece;

    if (model == NULL || clips == NULL ||
        tile_x >= PAGER_SCENE_TILE_COUNT ||
        tile_y >= PAGER_SCENE_TILE_COUNT ||
        model->petal_layer_opacity == 0U) {
        return 0U;
    }
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        if (model->pieces[piece].opacity != 0U &&
            rectangles_intersect(
                left, top, right, bottom, &clips[piece])) {
            mask |= (uint8_t)(1U << piece);
        }
    }
    return mask;
}

bool pager_scene_tile_full_layer_active(
    const pager_blossom_model_t *model, uint8_t tile_x, uint8_t tile_y) {
    int16_t left;
    int16_t top;
    int16_t right;
    int16_t bottom;
    pager_scene_piece_clip_t clip;

    if (model == NULL ||
        tile_x >= PAGER_SCENE_TILE_COUNT ||
        tile_y >= PAGER_SCENE_TILE_COUNT) {
        return false;
    }
    if (model->ordered_orbit && model->petal_layer_opacity != 0U) {
        return true;
    }
    if (model->full_layer_opacity == 0U ||
        model->pieces[0].opacity == 0U) {
        return false;
    }
    left = (int16_t)(
        PAGER_SCENE_REGION_X + tile_x * PAGER_SCENE_TILE_SIZE);
    top = (int16_t)(
        PAGER_SCENE_REGION_Y + tile_y * PAGER_SCENE_TILE_SIZE);
    right = (int16_t)(left + PAGER_SCENE_TILE_SIZE - 1U);
    bottom = (int16_t)(top + PAGER_SCENE_TILE_SIZE - 1U);
    clip = full_layer_clip(model);
    return rectangles_intersect(left, top, right, bottom, &clip);
}

void pager_scene_prepare_render_context(
    const pager_blossom_model_t *model,
    const char *balance,
    uint8_t ghost_count,
    const uint8_t ghost_opacity[PAGER_MULTI_GHOST_MAX],
    uint32_t motion_ms,
    pager_scene_render_context_t *context) {
    uint16_t value_width;
    uint8_t piece;

    if (model == NULL || context == NULL) {
        return;
    }
    memset(context, 0, sizeof(*context));
    context->value_length =
        (uint8_t)format_balance(balance, context->value_text);
    value_width = text_width(context->value_length, IDLE_VALUE_SCALE);
    context->value_left =
        (int16_t)(PAGER_SCENE_CENTER_X - (int16_t)(value_width / 2U));
    context->value_top =
        (int16_t)(PAGER_SCENE_CENTER_Y -
                  (int16_t)(TINY_FONT_HEIGHT * IDLE_VALUE_SCALE / 2U));
    context->balance_opacity = model->balance_opacity;
    context->petals_visible =
        model->petal_layer_opacity != 0U && !model->ordered_orbit;
    context->full_visible =
        model->full_layer_opacity != 0U ||
        (model->ordered_orbit && model->petal_layer_opacity != 0U);

    if (model->ordered_orbit && model->petal_layer_opacity != 0U) {
        context->full = make_mask_layer_at(
            model->composite_angle_q8,
            4096U,
            PAGER_BLOSSOM_READY_COLOR,
            model->petal_layer_opacity,
            PAGER_SCENE_CENTER_X,
            PAGER_SCENE_CENTER_Y,
            g_blossom_ready_alpha_4bpp,
            BLOSSOM_READY_MASK_SIZE,
            PAGER_SCENE_REGION_SIZE);
        return;
    }

    if (context->petals_visible) {
        for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
            const pager_blossom_piece_pose_t *pose = &model->pieces[piece];
            const uint16_t opacity =
                ((uint16_t)pose->opacity *
                 model->petal_layer_opacity + 127U) / 255U;

            context->pieces[piece] = make_layer_at(
                pose->angle_q8,
                pose->scale_q12,
                pose->color,
                (uint8_t)opacity,
                (int16_t)((pose->center_x_q8 + 128) >> 8U),
                (int16_t)((pose->center_y_q8 + 128) >> 8U));
            context->pieces[piece].mask_4bpp =
                g_blossom_piece_alpha_4bpp[piece];
        }
    }
    if (context->full_visible) {
        const pager_blossom_piece_pose_t *pose = &model->pieces[0];
        const uint16_t opacity =
            ((uint16_t)pose->opacity * model->full_layer_opacity + 127U) /
            255U;

        context->full = make_layer_at(
            pose->angle_q8,
            pose->scale_q12,
            model->full_layer_color,
            (uint8_t)opacity,
            PAGER_SCENE_CENTER_X,
            PAGER_SCENE_CENTER_Y);
    }
    context->ghost_count = ghost_count > PAGER_MULTI_GHOST_MAX
        ? PAGER_MULTI_GHOST_MAX
        : ghost_count;
    for (piece = 0U; piece < context->ghost_count; ++piece) {
        const int32_t direction = (piece & 1U) == 0U ? -1 : 1;
        const int16_t angle_q8 = (int16_t)(direction * (int32_t)(
            ((motion_ms % g_ghost_period_ms[piece]) * 65536U) /
            g_ghost_period_ms[piece]));
        const uint16_t scale = (uint16_t)(((uint32_t)
            model->pieces[0].scale_q12 * g_ghost_scale_ratio_q12[piece] +
            2048U) >> 12U);
        const uint16_t colors[PAGER_MULTI_GHOST_MAX] = {
            pager_scene_rgb565(64U, 92U, 238U),
            pager_scene_rgb565(112U, 86U, 244U),
            pager_scene_rgb565(76U, 180U, 224U)};
        const uint8_t transition = ghost_opacity == NULL
            ? 0U
            : ghost_opacity[piece];
        const uint8_t opacity = (uint8_t)(((uint16_t)
            g_ghost_base_opacity[piece] * transition + 127U) / 255U);

        context->ghosts[piece] = make_layer_at(
            angle_q8,
            scale,
            colors[piece],
            opacity,
            PAGER_SCENE_CENTER_X,
            PAGER_SCENE_CENTER_Y);
    }
}

void pager_scene_render_prepared_span(
    pager_state_t state,
    uint32_t elapsed_ms,
    const pager_scene_render_context_t *context,
    uint8_t active_piece_mask,
    bool full_layer_active,
    int16_t x_start,
    int16_t y,
    uint16_t pixel_count,
    uint16_t *pixels) {
    logo_sampler_t samplers[BLOSSOM_PIECE_COUNT];
    logo_sampler_t full_sampler = {0};
    logo_sampler_t ghost_samplers[PAGER_MULTI_GHOST_MAX];
    const bool petals_visible =
        context != NULL && context->petals_visible &&
        active_piece_mask != 0U;
    const bool full_visible =
        context != NULL && context->full_visible &&
        full_layer_active;
    uint8_t piece;
    uint16_t pixel;

    (void)elapsed_ms;
    if (context == NULL || pixels == NULL) {
        return;
    }
    if (petals_visible) {
        for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
            if ((active_piece_mask & (uint8_t)(1U << piece)) == 0U) {
                continue;
            }
            samplers[piece] = init_span_sampler(
                &context->pieces[piece], x_start, y);
        }
    }
    if (full_visible) {
        full_sampler = init_span_sampler(
            &context->full, x_start, y);
    }
    for (piece = 0U; piece < context->ghost_count; ++piece) {
        ghost_samplers[piece] = init_span_sampler(
            &context->ghosts[piece], x_start, y);
    }

    for (pixel = 0U; pixel < pixel_count; ++pixel) {
        const int16_t x = (int16_t)(x_start + pixel);
        uint16_t color = pager_scene_background_color(
            state, 0U, x, y);

        if (pager_scene_is_hex_outline(x, y)) {
            color = pager_scene_hex_color();
        }
        for (piece = 0U; piece < context->ghost_count; ++piece) {
            const uint8_t alpha = sampler_alpha(&ghost_samplers[piece]);

            if (alpha != 0U) {
                color = blend565(color, context->ghosts[piece].color, alpha);
            }
        }
        if (petals_visible) {
            for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
                uint8_t alpha;

                if ((active_piece_mask & (uint8_t)(1U << piece)) == 0U) {
                    continue;
                }
                alpha = sampler_alpha(&samplers[piece]);
                if (alpha != 0U) {
                    color = blend565(
                        color, context->pieces[piece].color, alpha);
                }
            }
        }
        if (full_visible) {
            const uint8_t alpha = sampler_alpha(&full_sampler);

            if (alpha != 0U) {
                color = blend565(color, context->full.color, alpha);
            }
        }
        if (context->balance_opacity != 0U &&
            context->value_length != 0U &&
            sample_text(
                context->value_text,
                context->value_length,
                context->value_left,
                context->value_top,
                IDLE_VALUE_SCALE,
                x,
                y)) {
            const uint8_t alpha4 =
                (uint8_t)((context->balance_opacity * 15U + 127U) / 255U);
            color = blend565(
                color, pager_scene_rgb565(230U, 234U, 248U), alpha4);
        }
        pixels[pixel] = color;
    }
}

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
    uint16_t *pixels) {
    pager_scene_render_context_t context;

    if (model == NULL || pixels == NULL) {
        return;
    }
    pager_scene_prepare_render_context(
        model, balance, 0U, NULL, 0U, &context);
    pager_scene_render_prepared_span(
        state,
        elapsed_ms,
        &context,
        active_piece_mask,
        full_layer_active,
        x_start,
        y,
        pixel_count,
        pixels);
}

void pager_scene_render_motion_row(
    pager_state_t state,
    uint32_t elapsed_ms,
    const pager_blossom_model_t *model,
    const pager_scene_piece_clip_t clips[BLOSSOM_PIECE_COUNT],
    const char *balance,
    int16_t y,
    uint16_t *pixels) {
    (void)clips;
    pager_scene_render_motion_span(
        state,
        elapsed_ms,
        model,
        (uint8_t)((1U << BLOSSOM_PIECE_COUNT) - 1U),
        true,
        balance,
        PAGER_SCENE_REGION_X,
        y,
        PAGER_SCENE_REGION_SIZE,
        pixels);
}

void pager_scene_render_row(
    pager_state_t state,
    uint32_t elapsed_ms,
    const char *balance,
    int16_t y,
    uint16_t *pixels) {
    logo_layer_t layers[4];
    logo_sampler_t samplers[4];
    uint16_t ghost_row[PAGER_SCENE_REGION_SIZE];
    pager_scene_pose_t pose = pager_scene_pose(state, elapsed_ms);
    const pager_idle_layout_t idle_layout =
        pager_scene_idle_layout(state == PAGER_IDLE ? balance : NULL);
    uint8_t layer_count = 1U;
    uint8_t main_layer;
    uint16_t pixel;

    if (pixels == NULL) {
        return;
    }
    if (state == PAGER_MULTI) {
        layers[0] = make_layer(
            (uint8_t)(20U - elapsed_ms * 256U / 5600U),
            (uint16_t)(pose.scale_q12 + pose.scale_q12 / 12U),
            pager_scene_rgb565(155U, 138U, 251U), 54U);
        layers[1] = make_layer(
            (uint8_t)(42U + elapsed_ms * 256U / 4800U),
            (uint16_t)(pose.scale_q12 + pose.scale_q12 / 6U),
            pager_scene_rgb565(107U, 140U, 255U), 42U);
        layers[2] = make_layer(
            (uint8_t)(228U - elapsed_ms * 256U / 6400U),
            (uint16_t)(pose.scale_q12 + pose.scale_q12 / 4U),
            pager_scene_rgb565(84U, 199U, 236U), 32U);
        layer_count = 4U;
    }
    if (state == PAGER_IDLE && idle_layout.visible) {
        pose.scale_q12 = 2294U;
    }
    main_layer = (uint8_t)(layer_count - 1U);
    layers[main_layer] = state == PAGER_IDLE && idle_layout.visible
        ? make_layer_at(
              (int16_t)((uint16_t)pose.angle << 8U),
              pose.scale_q12,
              pager_scene_logo_color(state),
              pose.opacity,
              PAGER_SCENE_CENTER_X,
              IDLE_LOGO_CENTER_Y)
        : make_layer(
              pose.angle,
              pose.scale_q12,
              pager_scene_logo_color(state),
              pose.opacity);
    samplers[main_layer] = init_sampler(
        &layers[main_layer], PAGER_SCENE_REGION_X, y);

    for (pixel = 0U; pixel < PAGER_SCENE_REGION_SIZE; ++pixel) {
        ghost_row[pixel] = pager_scene_background_color(
            state,
            elapsed_ms,
            (int16_t)(PAGER_SCENE_REGION_X + pixel),
            y);
    }
    if (state == PAGER_MULTI && ((y - PAGER_SCENE_REGION_Y) & 1) == 0) {
        uint8_t layer;
        for (layer = 0U; layer < main_layer; ++layer) {
            samplers[layer] = init_sampler(
                &layers[layer], PAGER_SCENE_REGION_X, y);
        }
        for (pixel = 0U; pixel < PAGER_SCENE_REGION_SIZE; pixel += 2U) {
            uint16_t ghost_color = ghost_row[pixel];
            for (layer = 0U; layer < main_layer; ++layer) {
                const uint8_t alpha = sampler_alpha(&samplers[layer]);
                if (alpha != 0U) {
                    ghost_color = blend565(
                        ghost_color, layers[layer].color, alpha);
                }
                sampler_skip(&samplers[layer]);
            }
            ghost_row[pixel] = ghost_color;
            if (pixel + 1U < PAGER_SCENE_REGION_SIZE) {
                ghost_row[pixel + 1U] = ghost_color;
            }
        }
    }

    for (pixel = 0U; pixel < PAGER_SCENE_REGION_SIZE; ++pixel) {
        const int32_t x = PAGER_SCENE_REGION_X + pixel;
        uint16_t color = ghost_row[pixel];
        const uint8_t alpha = sampler_alpha(&samplers[main_layer]);

        if (pager_scene_is_hex_outline((int16_t)x, y)) {
            color = pager_scene_hex_color();
        }
        if (alpha != 0U) {
            color = blend565(color, layers[main_layer].color, alpha);
        }
        if (state == PAGER_IDLE && idle_layout.visible) {
            static const char week[] = "WEEK";
            char value_text[5];
            const size_t value_length = format_balance(balance, value_text);
            const int16_t week_left = (int16_t)(
                PAGER_SCENE_CENTER_X -
                (int16_t)(text_width(4U, IDLE_WEEK_SCALE) / 2U));

            if (sample_text(
                    week,
                    4U,
                    week_left,
                    IDLE_WEEK_TOP,
                    IDLE_WEEK_SCALE,
                    (int16_t)x,
                    y)) {
                color = pager_scene_rgb565(172U, 180U, 208U);
            } else if (sample_text(
                           value_text,
                           value_length,
                           idle_layout.value_left,
                           IDLE_VALUE_TOP,
                           IDLE_VALUE_SCALE,
                           (int16_t)x,
                           y)) {
                color = pager_scene_rgb565(126U, 96U, 255U);
            }
        }
        pixels[pixel] = color;
    }
}
