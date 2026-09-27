cmake_minimum_required(VERSION 3.16)

project(codex_pager_host_tests C)

enable_testing()

add_executable(test_pager_core
    test_pager_core.c
    ../firmware/src/pager_core.c
    ../firmware/src/pager_stream.c
    ../firmware/src/led_effects.c
    ../firmware/src/display_pattern.c
    ../firmware/src/blossom_motion.c
    ../firmware/src/buzzer.c
    ../firmware/src/display_scene.c
    ../firmware/src/tiny_font.c
    ../firmware/src/st7789_profile.c
    ../../../Core/Src/blossom_asset.c
)

target_include_directories(test_pager_core PRIVATE
    ../firmware/include
    ../../../Core/Inc
)

if(MSVC)
    target_compile_options(test_pager_core PRIVATE /W4 /WX)
else()
    target_compile_options(test_pager_core PRIVATE -Wall -Wextra -Werror)
endif()

add_test(NAME pager_core COMMAND test_pager_core)
set_tests_properties(pager_core PROPERTIES TIMEOUT 5)
