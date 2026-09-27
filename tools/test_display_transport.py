from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "Core" / "Src" / "oled.c").read_text(
    encoding="ascii"
)
MAKEFILE = (Path(__file__).resolve().parents[1] / "Makefile").read_text(encoding="ascii")
ASSET_HEADER = (Path(__file__).resolve().parents[1] / "Core" / "Inc" / "blossom_asset.h").read_text(
    encoding="ascii"
)
MAIN_SOURCE = (Path(__file__).resolve().parents[1] / "Core" / "Src" / "main.c").read_text(
    encoding="ascii"
)


def test_display_uses_spi2_hardware_and_scanline_buffer():
    assert "__HAL_RCC_SPI2_CLK_ENABLE()" in SOURCE
    assert "GPIO_MODE_AF_PP" in SOURCE
    assert "static uint8_t scanline[UI_REGION_SIZE * 2U]" in SOURCE
    assert "spi_write_buffer(scanline" in SOURCE
    assert "for (uint16_t mask = 0x8000U; mask; mask >>= 1)" not in SOURCE


def test_spi_clock_is_limited_for_breadboard_wiring():
    assert "SPI_CR1_BR_0" in SOURCE


def test_diagnostic_build_uses_known_good_software_spi_path():
    assert "#define LCD_SOFTWARE_SPI 1" in SOURCE
    assert "#define LCD_SOFT_SPI_DELAY_CYCLES 24U" in SOURCE
    assert "soft_spi_delay" in SOURCE


def test_diagnostic_build_draws_static_rgb_bars():
    assert "#define LCD_COLORBAR_DIAGNOSTIC 1" in SOURCE
    assert "RGB565(255, 0, 0)" in SOURCE
    assert "RGB565(0, 255, 0)" in SOURCE
    assert "RGB565(0, 0, 255)" in SOURCE


def test_display_signal_pins_use_pb5_to_pb9_mapping():
    assert "#define LCD_SCL_PIN GPIO_PIN_9" in SOURCE
    assert "#define LCD_SDA_PIN GPIO_PIN_8" in SOURCE
    assert "#define LCD_RES_PIN GPIO_PIN_7" in SOURCE
    assert "#define LCD_DC_PIN GPIO_PIN_6" in SOURCE
    assert "#define LCD_BLK_PIN GPIO_PIN_5" in SOURCE


def test_colorbar_diagnostic_pulses_backlight_for_wiring_check():
    assert "LCD_BACKLIGHT_DIAGNOSTIC_MS 1000U" in SOURCE
    assert "LCD_GPIO->ODR & LCD_BLK_PIN" in SOURCE


def test_st7789_exits_sleep_before_display_configuration():
    assert SOURCE.index("lcd_cmd(0x11);") < SOURCE.index("lcd_cmd(0x3A);")
    assert "lcd_cmd(0x13);" in SOURCE
    assert "lcd_cmd(0x29);\n  HAL_Delay(20);" in SOURCE


def test_usb_reconnect_occurs_after_blocking_display_startup():
    assert MAIN_SOURCE.index("\n  OLED_Init();") < MAIN_SOURCE.index(
        "\n  USB_ReconnectPulse();"
    )


def test_running_palette_is_visibly_blue_purple():
    assert "RGB565(146, 132, 255)" in SOURCE
    assert "RGB565(92, 112, 255)" in SOURCE


def test_release_firmware_optimizes_pixel_math():
    assert "-O2" in MAKEFILE
    assert "-Og" not in MAKEFILE


def test_rotation_coordinates_advance_incrementally_across_each_row():
    assert "logo_sampler_t" in SOURCE
    assert "init_sampler" in SOURCE
    assert "sampler_alpha" in SOURCE
    assert "layer_alpha(&layers[layer], x, y)" not in SOURCE


def test_translucent_multi_task_ghosts_use_low_cost_sampling_only():
    assert "sample_mask_nearest_q8" in SOURCE
    assert "layer == layer_count - 1U" not in SOURCE


def test_compact_antialiased_mask_avoids_bilinear_cost_for_primary_logo():
    assert "#define BLOSSOM_MASK_SIZE 128U" in ASSET_HEADER
    assert "#define BLOSSOM_MASK_BYTES 8192U" in ASSET_HEADER
    assert "init_sampler(&layers[layer], y)" in SOURCE
    assert "sample_mask_q8" not in SOURCE


def test_ambient_background_is_computed_once_per_scanline():
    assert "background_row_color" in SOURCE
    assert "background_pixel" not in SOURCE


def test_multi_task_ghosts_are_cached_at_two_by_two_resolution():
    assert "ghost_row[UI_REGION_SIZE]" in SOURCE
    assert "pixel += 2U" in SOURCE
    assert "sampler_skip" in SOURCE
