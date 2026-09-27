#ifndef CODEX_TINY_FONT_H
#define CODEX_TINY_FONT_H

#include <stdbool.h>
#include <stdint.h>

#define TINY_FONT_WIDTH 5U
#define TINY_FONT_HEIGHT 7U

bool tiny_font_sample(char glyph, uint8_t x, uint8_t y);

#endif
