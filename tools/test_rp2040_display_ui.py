from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_SOURCE = (ROOT / "ports/rp2040-zero/firmware/src/main.c").read_text(
    encoding="ascii"
)
UI_HEADER = (ROOT / "ports/rp2040-zero/firmware/include/display_ui.h").read_text(
    encoding="ascii"
)
UI_SOURCE = (ROOT / "ports/rp2040-zero/firmware/src/display_ui.c").read_text(
    encoding="ascii"
)
SCENE_SOURCE = (ROOT / "ports/rp2040-zero/firmware/src/display_scene.c").read_text(
    encoding="ascii"
)
PIO_SOURCE = (ROOT / "ports/rp2040-zero/firmware/src/st7789_spi.pio").read_text(
    encoding="ascii"
)
BOARD_CONFIG = (
    ROOT / "ports/rp2040-zero/firmware/include/board_config.h"
).read_text(encoding="ascii")
SCENE_HEADER = (
    ROOT / "ports/rp2040-zero/firmware/include/display_scene.h"
).read_text(encoding="ascii")


def test_state_change_uses_motion_and_delta_buffers_without_transition_fill():
    set_state = UI_SOURCE.split("void pager_display_ui_set_state", 1)[1].split(
        "void pager_display_ui_update", 1
    )[0]
    assert "pager_blossom_motion_t blossom_motion" in UI_SOURCE
    assert "pager_blossom_motion_set_target" in set_state
    assert "scene_frame_t frame_buffers[2]" in UI_SOURCE
    assert "static uint32_t transition_started_ms" not in UI_SOURCE
    assert "st7789_fill" not in set_state


def test_each_animation_frame_uses_verified_byte_transport():
    render_frame = UI_SOURCE.split("static void render_frame", 1)[1].split(
        "void pager_display_ui_init", 1
    )[0]
    assert "st7789_write_packed_pixels" not in UI_SOURCE
    assert "send_delta_frame" in UI_SOURCE
    assert render_frame.count("send_delta_frame") == 1


def test_display_bus_runs_at_forty_eight_megahertz():
    assert "#define PAGER_DISPLAY_SPI_HZ 48000000U" in BOARD_CONFIG


def test_pio_uses_the_verified_eight_bit_word_path():
    assert "set x, 7" in PIO_SOURCE
    assert "mov x, y" not in PIO_SOURCE


def test_all_states_share_a_canvas_color_to_avoid_transition_borders():
    base_function = SCENE_SOURCE.split("uint16_t pager_scene_base_color", 1)[1].split(
        "static uint16_t accent_color", 1
    )[0]
    assert "if (state" not in base_function.split("{", 1)[1]


def test_scene_region_is_centered_on_the_240_square_display():
    assert "#define PAGER_SCENE_CENTER_X 120" in SCENE_HEADER
    assert "#define PAGER_SCENE_CENTER_Y 120" in SCENE_HEADER
    assert "#define PAGER_SCENE_REGION_X 6" in SCENE_HEADER
    assert "#define PAGER_SCENE_REGION_Y 6" in SCENE_HEADER
    assert "#define PAGER_SCENE_REGION_SIZE 228U" in SCENE_HEADER


def test_petal_transport_uses_separate_coalesced_tile_runs():
    assert "#define PAGER_SCENE_TILE_SIZE 12U" in SCENE_HEADER
    assert "send_dirty_tiles" in UI_SOURCE
    assert "pager_scene_tile_dirty" in UI_SOURCE
    assert "DELTA_BAND_ROWS" not in UI_SOURCE
    assert "run_first_tile" in UI_SOURCE
    assert "run_last_tile" in UI_SOURCE


def test_ordered_ready_composite_uses_sparse_dirty_tiles():
    render_frame = UI_SOURCE.split("static void render_frame", 1)[1].split(
        "void pager_display_ui_init", 1
    )[0]
    previous_visibility = render_frame.split(
        "const bool previous_petals_visible =", 1
    )[1].split(";", 1)[0]
    current_visibility = render_frame.split(
        "current_petals_visible =", 1
    )[1].split(";", 1)[0]
    assert "ordered_orbit" not in previous_visibility
    assert "ordered_orbit" not in current_visibility
    assert "model.petal_layer_opacity != 0U;" in render_frame


def test_petal_renderer_uses_compact_active_layer_masks():
    assert "pager_scene_render_motion_span" in SCENE_SOURCE
    assert "active_piece_mask" in SCENE_SOURCE
    assert "pager_scene_tile_layer_mask" in UI_SOURCE


def test_render_layers_are_precomputed_once_per_frame():
    assert "pager_scene_prepare_render_context" in UI_SOURCE
    render_scene = UI_SOURCE.split("static void render_scene", 1)[1].split(
        "static void send_frame", 1
    )[0]
    dirty_scene = UI_SOURCE.split("static void render_dirty_tiles", 1)[1].split(
        "static void send_dirty_tiles", 1
    )[0]
    assert render_scene.count("pager_scene_prepare_render_context") == 1
    assert dirty_scene.count("pager_scene_prepare_render_context") == 1
    assert "pager_scene_render_prepared_span" in render_scene
    assert "pager_scene_render_prepared_span" in dirty_scene


def test_balance_changes_mark_the_center_tiles_dirty():
    assert "static bool balance_dirty" in UI_SOURCE
    assert "pager_scene_mark_balance_tiles(&dirty)" in UI_SOURCE
    assert "balance_dirty = true" in UI_SOURCE


def test_entering_ready_composite_uses_a_complete_frame_handoff():
    assert "current_ready_composite" in UI_SOURCE
    handoff = UI_SOURCE.split(
        "current_ready_composite && previous_individual_petals", 1
    )[1].split("} else if", 1)[0]
    assert "render_scene(working" in handoff
    assert "send_frame(working)" in handoff


def test_motion_renderer_skips_invisible_logo_layers():
    assert "const bool petals_visible" in SCENE_SOURCE
    assert "const bool full_visible" in SCENE_SOURCE
    assert "if (petals_visible)" in SCENE_SOURCE
    assert "if (full_visible)" in SCENE_SOURCE


def test_full_blossom_always_rotates_around_screen_center():
    full_layer_block = SCENE_SOURCE.split(
        "context->full = make_layer_at(", 1
    )[1].split(");", 1)[0]
    assert "PAGER_SCENE_CENTER_X" in full_layer_block
    assert "PAGER_SCENE_CENTER_Y" in full_layer_block
    assert "pose->center_x_q8" not in full_layer_block
    assert "pose->center_y_q8" not in full_layer_block


def test_main_forwards_running_count_to_display_snapshot():
    assert "state, snapshot.running, snapshot.balance, current_ms" in MAIN_SOURCE


def test_snapshot_api_accepts_running_count():
    assert "pager_state_t state," in UI_HEADER
    assert "uint32_t running_count," in UI_HEADER


def test_running_multi_switch_does_not_retarget_foreground_motion():
    assert "running_family_change" in UI_SOURCE
    assert "if (!running_family_change)" in UI_SOURCE


def test_main_configures_active_low_buzzer_on_gp14():
    assert "gpio_init(PAGER_BUZZER_PIN)" in MAIN_SOURCE
    assert "gpio_put(PAGER_BUZZER_PIN, true)" in MAIN_SOURCE
    assert "gpio_put(PAGER_BUZZER_PIN, !pager_buzzer_is_active" in MAIN_SOURCE
