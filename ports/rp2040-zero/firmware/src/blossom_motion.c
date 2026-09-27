#include "blossom_motion.h"

#include <stddef.h>
#include <string.h>

#define CENTER_Q8 (120 * 256)
#define FULL_SCALE_Q12 3604U
#define READY_RADIUS_Q8 (68 * 256)
#define ASSEMBLED_RADIUS_Q8 (32 * 256)
#define ASSEMBLED_PETAL_OFFSET_Q8 (24 * 256)
#define READY_SCALE_Q12 FULL_SCALE_Q12
#define READY_PETAL_CLOCKWISE_Q8 (32 * 256)
#define GENERIC_TRANSITION_MS 650U

static int16_t sin_q15_interpolated(uint16_t angle_q8) {
    const uint8_t index = (uint8_t)(angle_q8 >> 8U);
    const uint8_t fraction = (uint8_t)angle_q8;
    const int32_t from = g_sin_q15[index];
    const int32_t to = g_sin_q15[(uint8_t)(index + 1U)];

    return (int16_t)(
        from + ((to - from) * fraction + 128) / 256);
}

static uint16_t smooth_q15(uint32_t elapsed, uint32_t duration) {
    uint32_t time_q15;

    if (elapsed >= duration) {
        return 32768U;
    }
    time_q15 = (elapsed << 15U) / duration;
    return (uint16_t)(((uint64_t)time_q15 * time_q15 *
        (3U * 32768U - 2U * time_q15)) >> 30U);
}

static uint16_t ease_out_q15(uint32_t elapsed, uint32_t duration) {
    uint32_t time_q15;
    uint32_t remaining_q15;

    if (elapsed >= duration) {
        return 32768U;
    }
    time_q15 = (elapsed << 15U) / duration;
    remaining_q15 = 32768U - time_q15;
    return (uint16_t)(32768U -
        (uint32_t)(((uint64_t)remaining_q15 * remaining_q15 *
                    remaining_q15) >> 30U));
}

static int32_t scale_delta_q15(int32_t delta, uint16_t amount_q15) {
    const int32_t rounding = delta < 0 ? -16384 : 16384;

    return (delta * amount_q15 + rounding) / 32768;
}

static int16_t lerp_i16(int16_t from, int16_t to, uint16_t amount_q15) {
    return (int16_t)(
        from + scale_delta_q15((int32_t)to - from, amount_q15));
}

static int32_t lerp_i32(int32_t from, int32_t to, uint16_t amount_q15) {
    return from + scale_delta_q15(to - from, amount_q15);
}

static uint16_t lerp_u16(
    uint16_t from, uint16_t to, uint16_t amount_q15) {
    return (uint16_t)(
        (int32_t)from +
        scale_delta_q15((int32_t)to - from, amount_q15));
}

static uint8_t lerp_u8(uint8_t from, uint8_t to, uint16_t amount_q15) {
    return (uint8_t)(
        (int32_t)from +
        scale_delta_q15((int32_t)to - from, amount_q15));
}

static uint16_t lerp_color565(
    uint16_t from, uint16_t to, uint16_t amount_q15) {
    const uint16_t from_red = (from >> 11U) & 0x1FU;
    const uint16_t from_green = (from >> 5U) & 0x3FU;
    const uint16_t from_blue = from & 0x1FU;
    const uint16_t to_red = (to >> 11U) & 0x1FU;
    const uint16_t to_green = (to >> 5U) & 0x3FU;
    const uint16_t to_blue = to & 0x1FU;
    const uint16_t red = lerp_u16(from_red, to_red, amount_q15);
    const uint16_t green = lerp_u16(from_green, to_green, amount_q15);
    const uint16_t blue = lerp_u16(from_blue, to_blue, amount_q15);

    return (uint16_t)((red << 11U) | (green << 5U) | blue);
}

static void fill_piece(
    pager_blossom_piece_pose_t *piece,
    int32_t center_x_q8,
    int32_t center_y_q8,
    int16_t angle_q8,
    uint16_t scale_q12,
    uint16_t color) {
    piece->center_x_q8 = center_x_q8;
    piece->center_y_q8 = center_y_q8;
    piece->angle_q8 = angle_q8;
    piece->scale_q12 = scale_q12;
    piece->color = color;
    piece->opacity = 255U;
}

static void assembled_model(
    pager_blossom_model_t *model,
    uint16_t color,
    int16_t angle_q8) {
    const uint16_t group_angle_q8 = (uint16_t)angle_q8;
    uint8_t piece;

    memset(model, 0, sizeof(*model));
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        const uint16_t piece_step_q8 = (uint16_t)(
            (((uint16_t)piece * 256U) / BLOSSOM_PIECE_COUNT) << 8U);
        const uint16_t position_angle_q8 = (uint16_t)(
            group_angle_q8 + 192U * 256U - piece_step_q8);
        const uint16_t petal_angle_q8 = (uint16_t)(
            group_angle_q8 - piece_step_q8 +
            ASSEMBLED_PETAL_OFFSET_Q8);
        const int16_t cosine = sin_q15_interpolated(
            (uint16_t)(position_angle_q8 + 64U * 256U));
        const int16_t sine =
            sin_q15_interpolated(position_angle_q8);
        fill_piece(
            &model->pieces[piece],
            CENTER_Q8 +
                ((int32_t)cosine * ASSEMBLED_RADIUS_Q8 >> 15U),
            CENTER_Q8 +
                ((int32_t)sine * ASSEMBLED_RADIUS_Q8 >> 15U),
            (int16_t)petal_angle_q8,
            FULL_SCALE_Q12,
            color);
    }
    model->petal_layer_opacity = 0U;
    model->full_layer_opacity = 255U;
    model->full_layer_color = color;
    model->composite_angle_q8 = angle_q8;
}

static void ready_model(pager_blossom_model_t *model, uint32_t elapsed_ms) {
    const uint16_t phase_q8 = (uint16_t)(
        ((uint64_t)(elapsed_ms % 18000U) * 65536U) / 18000U);
    uint8_t piece;

    memset(model, 0, sizeof(*model));
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        const uint16_t piece_step_q8 = (uint16_t)(
            (((uint16_t)piece * 256U) / BLOSSOM_PIECE_COUNT) << 8U);
        const uint16_t angle_q8 = (uint16_t)(
            phase_q8 + 192U * 256U - piece_step_q8);
        const int16_t cosine = sin_q15_interpolated(
            (uint16_t)(angle_q8 + 64U * 256U));
        const int16_t sine = sin_q15_interpolated(angle_q8);
        fill_piece(
            &model->pieces[piece],
            CENTER_Q8 + ((int32_t)cosine * READY_RADIUS_Q8 >> 15U),
            CENTER_Q8 + ((int32_t)sine * READY_RADIUS_Q8 >> 15U),
            (int16_t)(angle_q8 + READY_PETAL_CLOCKWISE_Q8),
            READY_SCALE_Q12,
            PAGER_BLOSSOM_READY_COLOR);
    }
    model->balance_opacity = 255U;
    model->petal_layer_opacity = 255U;
    model->full_layer_opacity = 0U;
    model->full_layer_color = PAGER_BLOSSOM_READY_COLOR;
    model->composite_angle_q8 = (int16_t)phase_q8;
    model->ordered_orbit = true;
    model->angular_velocity_q8 = 5;
}

static void offline_model(pager_blossom_model_t *model, uint32_t elapsed_ms) {
    static const uint8_t start_x[BLOSSOM_PIECE_COUNT] =
        {55U, 91U, 132U, 174U, 111U, 190U};
    static const uint8_t start_y[BLOSSOM_PIECE_COUNT] =
        {35U, 58U, 27U, 49U, 18U, 68U};
    static const uint8_t settle_x[BLOSSOM_PIECE_COUNT] =
        {120U, 88U, 152U, 68U, 112U, 164U};
    static const uint8_t settle_y[BLOSSOM_PIECE_COUNT] =
        {197U, 174U, 174U, 148U, 148U, 148U};
    static const int16_t start_angle_q8[BLOSSOM_PIECE_COUNT] =
        {-38 * 256, 21 * 256, 73 * 256, -91 * 256, 116 * 256, 44 * 256};
    static const int16_t settle_angle_q8[BLOSSOM_PIECE_COUNT] =
        {19 * 256, -31 * 256, 47 * 256, -58 * 256, 76 * 256, 8 * 256};
    static const uint16_t delay_ms[BLOSSOM_PIECE_COUNT] =
        {0U, 70U, 145U, 35U, 205U, 110U};
    static const uint16_t fall_ms[BLOSSOM_PIECE_COUNT] =
        {720U, 790U, 750U, 840U, 810U, 770U};
    uint8_t piece;

    memset(model, 0, sizeof(*model));
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        const uint32_t local_ms =
            elapsed_ms > delay_ms[piece]
                ? elapsed_ms - delay_ms[piece] : 0U;
        const uint16_t fall_amount =
            local_ms >= fall_ms[piece] ? 32768U :
            (uint16_t)(((uint64_t)local_ms * local_ms * 32768U) /
                ((uint64_t)fall_ms[piece] * fall_ms[piece]));
        const uint16_t settle_amount = smooth_q15(
            local_ms, (uint32_t)fall_ms[piece] + 240U);
        int32_t center_x_q8 =
            (int32_t)start_x[piece] * 256 +
            scale_delta_q15(
                ((int32_t)settle_x[piece] - start_x[piece]) * 256,
                fall_amount);
        int32_t center_y_q8 =
            (int32_t)start_y[piece] * 256 +
            scale_delta_q15(
                ((int32_t)settle_y[piece] - start_y[piece]) * 256,
                fall_amount);

        if (local_ms < fall_ms[piece]) {
            const uint8_t sway_phase =
                (uint8_t)((local_ms * 160U) / fall_ms[piece]);
            center_x_q8 +=
                ((int32_t)g_sin_q15[sway_phase] * 4 * 256) >> 15U;
        } else if (local_ms < (uint32_t)fall_ms[piece] + 240U) {
            const uint32_t bounce_ms = local_ms - fall_ms[piece];
            const uint8_t bounce_phase =
                (uint8_t)((bounce_ms * 128U) / 240U);
            const int32_t bounce_height =
                8 - (int32_t)(bounce_ms * 5U / 240U);

            center_y_q8 -=
                ((int32_t)g_sin_q15[bounce_phase] *
                 bounce_height * 256) >> 15U;
        }
        fill_piece(
            &model->pieces[piece],
            center_x_q8,
            center_y_q8,
            lerp_i16(
                start_angle_q8[piece],
                settle_angle_q8[piece],
                settle_amount),
            FULL_SCALE_Q12,
            PAGER_BLOSSOM_OFFLINE_COLOR);
    }
    model->petal_layer_opacity = 255U;
    model->full_layer_opacity = 0U;
    model->full_layer_color = PAGER_BLOSSOM_OFFLINE_COLOR;
}

static void running_model(pager_blossom_model_t *model, uint32_t elapsed_ms) {
    const uint32_t cycle_ms = elapsed_ms % 2600U;
    const uint16_t linear_angle_q8 =
        (uint16_t)(((uint64_t)cycle_ms * 65536U) / 2600U);
    const uint8_t phase = (uint8_t)(linear_angle_q8 >> 8U);
    const int16_t speed_wave =
        g_sin_q15[(uint8_t)(phase + 64U)];
    const int32_t angle_wave_q8 =
        ((int32_t)g_sin_q15[phase] * (12 * 256)) >> 15U;
    const int32_t scale_wave =
        ((int32_t)g_sin_q15[phase] * 650) >> 15U;
    const uint16_t turn_q8 =
        (uint16_t)(linear_angle_q8 + angle_wave_q8);
    uint8_t piece;

    assembled_model(
        model, PAGER_BLOSSOM_RUNNING_COLOR, (int16_t)turn_q8);
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        model->pieces[piece].scale_q12 =
            (uint16_t)(FULL_SCALE_Q12 + scale_wave);
    }
    model->angular_velocity_q8 =
        (int16_t)(18 + ((int32_t)speed_wave * 7 >> 15U));
}

static void wait_model(pager_blossom_model_t *model, uint32_t elapsed_ms) {
    const uint32_t cycle_ms = elapsed_ms % 1600U;
    uint16_t pulse_q15 = 0U;
    uint8_t piece;

    if (cycle_ms < 180U) {
        pulse_q15 = (uint16_t)(
            g_sin_q15[(uint8_t)(cycle_ms * 128U / 180U)]);
    } else if (cycle_ms >= 260U && cycle_ms < 440U) {
        pulse_q15 = (uint16_t)(
            g_sin_q15[(uint8_t)((cycle_ms - 260U) * 128U / 180U)]);
    }
    assembled_model(model, PAGER_BLOSSOM_WAIT_COLOR, 0);
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        model->pieces[piece].scale_q12 =
            (uint16_t)(FULL_SCALE_Q12 +
                ((uint32_t)pulse_q15 * 360U >> 15U));
    }
}

static void steady_model(
    pager_state_t state,
    uint32_t elapsed_ms,
    pager_blossom_model_t *model) {
    if (state == PAGER_IDLE) {
        ready_model(model, elapsed_ms);
    } else if (state == PAGER_OFFLINE) {
        offline_model(model, elapsed_ms);
    } else if (state == PAGER_RUNNING || state == PAGER_MULTI) {
        running_model(model, elapsed_ms);
    } else if (state == PAGER_WAIT) {
        wait_model(model, elapsed_ms);
    } else if (state == PAGER_DONE) {
        assembled_model(model, PAGER_BLOSSOM_READY_COLOR, 0);
    } else {
        assembled_model(model, PAGER_BLOSSOM_READY_COLOR, 0);
    }
}

static void lerp_model(
    const pager_blossom_model_t *from,
    const pager_blossom_model_t *to,
    uint16_t amount_q15,
    pager_blossom_model_t *result) {
    uint8_t piece;

    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        result->pieces[piece].center_x_q8 = lerp_i32(
            from->pieces[piece].center_x_q8,
            to->pieces[piece].center_x_q8,
            amount_q15);
        result->pieces[piece].center_y_q8 = lerp_i32(
            from->pieces[piece].center_y_q8,
            to->pieces[piece].center_y_q8,
            amount_q15);
        result->pieces[piece].angle_q8 = lerp_i16(
            from->pieces[piece].angle_q8,
            to->pieces[piece].angle_q8,
            amount_q15);
        result->pieces[piece].scale_q12 = lerp_u16(
            from->pieces[piece].scale_q12,
            to->pieces[piece].scale_q12,
            amount_q15);
        result->pieces[piece].color = lerp_color565(
            from->pieces[piece].color,
            to->pieces[piece].color,
            amount_q15);
        result->pieces[piece].opacity = lerp_u8(
            from->pieces[piece].opacity,
            to->pieces[piece].opacity,
            amount_q15);
    }
    result->balance_opacity = lerp_u8(
        from->balance_opacity, to->balance_opacity, amount_q15);
    result->petal_layer_opacity = lerp_u8(
        from->petal_layer_opacity, to->petal_layer_opacity, amount_q15);
    result->full_layer_opacity = lerp_u8(
        from->full_layer_opacity, to->full_layer_opacity, amount_q15);
    result->full_layer_color = lerp_color565(
        from->full_layer_color, to->full_layer_color, amount_q15);
    result->composite_angle_q8 = lerp_i16(
        from->composite_angle_q8, to->composite_angle_q8, amount_q15);
    result->angular_velocity_q8 = lerp_i16(
        from->angular_velocity_q8, to->angular_velocity_q8, amount_q15);
    result->ordered_orbit = amount_q15 == 32768U
        ? to->ordered_orbit : from->ordered_orbit;
}

static void sample_ready_to_running(
    const pager_blossom_motion_t *motion,
    uint32_t elapsed,
    pager_blossom_model_t *model) {
    uint16_t gather_amount;
    uint16_t color_amount;
    uint16_t fade_amount = 0U;
    const uint16_t start_group_q8 =
        (uint16_t)motion->start.composite_angle_q8;
    uint32_t group_delta_q8 =
        (uint16_t)(0U - start_group_q8);
    int32_t group_angle_q8;
    int32_t radius_q8;
    int32_t petal_offset_q8;
    uint8_t piece;

    if (elapsed <= PAGER_READY_TO_RUNNING_MS) {
        if (group_delta_q8 < 64U * 256U) {
            group_delta_q8 += 256U * 256U;
        }
        gather_amount = smooth_q15(
            elapsed, PAGER_READY_TO_RUNNING_MS);
        group_angle_q8 =
            start_group_q8 +
            scale_delta_q15((int32_t)group_delta_q8, gather_amount);
        radius_q8 = READY_RADIUS_Q8 + scale_delta_q15(
            ASSEMBLED_RADIUS_Q8 - READY_RADIUS_Q8, gather_amount);
        petal_offset_q8 = (192 + 32) * 256 +
            scale_delta_q15(56 * 256, gather_amount);
        color_amount = ease_out_q15(elapsed, 300U);
        memset(model, 0, sizeof(*model));
        for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
            const uint16_t piece_step_q8 = (uint16_t)(
                (((uint16_t)piece * 256U) /
                 BLOSSOM_PIECE_COUNT) << 8U);
            const uint16_t position_angle_q8 = (uint16_t)(
                group_angle_q8 + 192U * 256U - piece_step_q8);
            const int16_t cosine = sin_q15_interpolated(
                (uint16_t)(position_angle_q8 + 64U * 256U));
            const int16_t sine =
                sin_q15_interpolated(position_angle_q8);

            fill_piece(
                &model->pieces[piece],
                CENTER_Q8 +
                    ((int32_t)cosine * radius_q8 >> 15U),
                CENTER_Q8 +
                    ((int32_t)sine * radius_q8 >> 15U),
                (int16_t)(
                    group_angle_q8 - piece_step_q8 +
                    petal_offset_q8),
                FULL_SCALE_Q12,
                lerp_color565(
                    PAGER_BLOSSOM_READY_COLOR,
                    PAGER_BLOSSOM_RUNNING_COLOR,
                    color_amount));
        }
        model->balance_opacity =
            (uint8_t)(255U -
                ((uint32_t)gather_amount * 255U >> 15U));
        model->composite_angle_q8 = (int16_t)group_angle_q8;
        model->ordered_orbit = false;
        if (elapsed > 520U) {
            fade_amount = smooth_q15(elapsed - 520U, 280U);
        }
        model->petal_layer_opacity =
            (uint8_t)(255U - ((uint32_t)fade_amount * 255U >> 15U));
        model->full_layer_opacity =
            (uint8_t)((uint32_t)fade_amount * 255U >> 15U);
        model->full_layer_color = PAGER_BLOSSOM_RUNNING_COLOR;
        return;
    }
    running_model(model, elapsed - PAGER_READY_TO_RUNNING_MS);
}

static void sample_running_to_ready(
    const pager_blossom_motion_t *motion,
    uint32_t elapsed,
    pager_blossom_model_t *model) {
    pager_blossom_model_t stopped;
    pager_blossom_model_t gathered;
    pager_blossom_model_t ready;
    uint8_t piece;

    assembled_model(
        &stopped,
        motion->start.pieces[0].color,
        motion->start.pieces[0].angle_q8);
    stopped.angular_velocity_q8 = 0;
    if (elapsed < 240U) {
        lerp_model(
            &motion->start, &stopped, smooth_q15(elapsed, 240U), model);
        return;
    }
    gathered = stopped;
    gathered.petal_layer_opacity = 255U;
    gathered.full_layer_opacity = 0U;
    for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
        gathered.pieces[piece].color = PAGER_BLOSSOM_READY_COLOR;
    }
    if (elapsed <= 400U) {
        lerp_model(
            &stopped,
            &gathered,
            smooth_q15(elapsed - 240U, 160U),
            model);
        for (piece = 0U; piece < BLOSSOM_PIECE_COUNT; ++piece) {
            model->pieces[piece].color = PAGER_BLOSSOM_READY_COLOR;
        }
        return;
    }
    if (elapsed <= PAGER_RUNNING_TO_READY_MS) {
        ready_model(&ready, 0U);
        lerp_model(
            &gathered,
            &ready,
            smooth_q15(elapsed - 400U, 800U),
            model);
        return;
    }
    ready_model(model, elapsed - PAGER_RUNNING_TO_READY_MS);
}

static void sample_offline_to_ready(
    const pager_blossom_motion_t *motion,
    uint32_t elapsed,
    pager_blossom_model_t *model) {
    pager_blossom_model_t ready;

    if (elapsed <= PAGER_OFFLINE_TO_READY_MS) {
        ready_model(&ready, 0U);
        lerp_model(
            &motion->start,
            &ready,
            smooth_q15(elapsed, PAGER_OFFLINE_TO_READY_MS),
            model);
        model->petal_layer_opacity = 255U;
        model->full_layer_opacity = 0U;
        return;
    }
    ready_model(model, elapsed - PAGER_OFFLINE_TO_READY_MS);
}

void pager_blossom_motion_init(
    pager_blossom_motion_t *motion,
    pager_state_t state,
    uint32_t now_ms) {
    if (motion == NULL) {
        return;
    }
    memset(motion, 0, sizeof(*motion));
    motion->source = state;
    motion->target = state;
    motion->started_ms = now_ms;
    steady_model(state, 0U, &motion->start);
    motion->current = motion->start;
}

void pager_blossom_motion_sample(
    pager_blossom_motion_t *motion,
    uint32_t now_ms,
    pager_blossom_model_t *model) {
    uint32_t elapsed;

    if (motion == NULL || model == NULL) {
        return;
    }
    elapsed = now_ms - motion->started_ms;
    if (motion->source == motion->target) {
        steady_model(motion->target, elapsed, model);
    } else if (motion->source == PAGER_IDLE &&
               (motion->target == PAGER_RUNNING ||
                motion->target == PAGER_MULTI)) {
        sample_ready_to_running(motion, elapsed, model);
    } else if ((motion->source == PAGER_RUNNING ||
                motion->source == PAGER_MULTI ||
                motion->source == PAGER_DONE) &&
               motion->target == PAGER_IDLE) {
        sample_running_to_ready(motion, elapsed, model);
    } else if (motion->source == PAGER_OFFLINE &&
               motion->target == PAGER_IDLE) {
        sample_offline_to_ready(motion, elapsed, model);
    } else {
        pager_blossom_model_t target;
        steady_model(motion->target, elapsed, &target);
        lerp_model(
            &motion->start,
            &target,
            smooth_q15(elapsed, GENERIC_TRANSITION_MS),
            model);
    }
    motion->current = *model;
}

void pager_blossom_motion_set_target(
    pager_blossom_motion_t *motion,
    pager_state_t target,
    uint32_t now_ms) {
    pager_blossom_model_t current;

    if (motion == NULL || target == motion->target) {
        return;
    }
    pager_blossom_motion_sample(motion, now_ms, &current);
    motion->start = current;
    motion->source = motion->target;
    motion->target = target;
    motion->started_ms = now_ms;
    motion->current = current;
}
