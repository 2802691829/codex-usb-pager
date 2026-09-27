cmake_minimum_required(VERSION 3.13)

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(codex_pager_rp2040 C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(codex_pager_rp2040
    src/main.c
    src/pager_core.c
    src/pager_stream.c
    src/led_effects.c
    src/display_pattern.c
    src/blossom_motion.c
    src/buzzer.c
    src/display_scene.c
    src/display_ui.c
    src/tiny_font.c
    src/st7789.c
    src/st7789_profile.c
    ../../../Core/Src/blossom_asset.c
)

pico_generate_pio_header(codex_pager_rp2040
    ${CMAKE_CURRENT_LIST_DIR}/src/ws2812.pio
)

pico_generate_pio_header(codex_pager_rp2040
    ${CMAKE_CURRENT_LIST_DIR}/src/st7789_spi.pio
)

target_include_directories(codex_pager_rp2040 PRIVATE
    include
    ../../../Core/Inc
)

target_compile_options(codex_pager_rp2040 PRIVATE
    -Wall
    -Wextra
    -Werror
)

target_link_libraries(codex_pager_rp2040 PRIVATE
    pico_stdlib
    hardware_dma
    hardware_pio
)

target_compile_definitions(codex_pager_rp2040 PRIVATE
    USBD_PRODUCT="Codex Pager"
)

pico_enable_stdio_usb(codex_pager_rp2040 1)
pico_enable_stdio_uart(codex_pager_rp2040 0)
pico_add_extra_outputs(codex_pager_rp2040)
