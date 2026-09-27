#ifndef CODEX_PAGER_STREAM_H
#define CODEX_PAGER_STREAM_H

#include "pager_core.h"

#include <stddef.h>

#define PAGER_STREAM_LINE_CAPACITY 96U
#define PAGER_STREAM_NO_BYTE (-1)

typedef int (*pager_stream_read_fn)(void *context);

typedef struct {
    char line[PAGER_STREAM_LINE_CAPACITY];
    size_t length;
} pager_stream_t;

size_t pager_stream_drain(
    pager_stream_t *stream,
    pager_stream_read_fn read_byte,
    void *context,
    pager_snapshot_t *latest_snapshot);

#endif
