#ifndef CODEX_USB_PAGER_BLOSSOM_ASSET_H
#define CODEX_USB_PAGER_BLOSSOM_ASSET_H

#include <stdint.h>

#define BLOSSOM_MASK_SIZE 128U
#define BLOSSOM_MASK_BYTES 8192U

#define BLOSSOM_PIECE_COUNT 6U
#define BLOSSOM_PIECE_ID_BYTES 8192U

#define BLOSSOM_READY_MASK_SIZE 456U
#define BLOSSOM_READY_MASK_BYTES 103968U

extern const uint8_t g_blossom_alpha_4bpp[BLOSSOM_MASK_BYTES];

extern const uint8_t g_blossom_piece_id_4bpp[BLOSSOM_PIECE_ID_BYTES];

extern const uint8_t g_blossom_piece_alpha_4bpp[BLOSSOM_PIECE_COUNT][BLOSSOM_MASK_BYTES];

extern const uint8_t g_blossom_ready_alpha_4bpp[BLOSSOM_READY_MASK_BYTES];

extern const uint8_t g_blossom_piece_min_x[BLOSSOM_PIECE_COUNT];
extern const uint8_t g_blossom_piece_min_y[BLOSSOM_PIECE_COUNT];
extern const uint8_t g_blossom_piece_max_x[BLOSSOM_PIECE_COUNT];
extern const uint8_t g_blossom_piece_max_y[BLOSSOM_PIECE_COUNT];
extern const uint8_t g_blossom_piece_radius[BLOSSOM_PIECE_COUNT];

extern const int16_t g_sin_q15[256];

#endif
