#include "pager_stream.h"

#include <stdbool.h>

static bool push_byte(
    pager_stream_t *stream, int byte, pager_snapshot_t *snapshot) {
    if (byte == '\r') {
        return false;
    }
    if (byte == '\n') {
        const bool valid = stream->length > 0U &&
                           pager_parse_line(stream->line, snapshot);
        stream->length = 0U;
        stream->line[0] = '\0';
        return valid;
    }
    if (byte < 32 || byte > 126 ||
        stream->length >= PAGER_STREAM_LINE_CAPACITY - 1U) {
        stream->length = 0U;
        stream->line[0] = '\0';
        return false;
    }
    stream->line[stream->length++] = (char)byte;
    stream->line[stream->length] = '\0';
    return false;
}

size_t pager_stream_drain(
    pager_stream_t *stream,
    pager_stream_read_fn read_byte,
    void *context,
    pager_snapshot_t *latest_snapshot) {
    size_t valid_count = 0U;
    int byte;

    if (stream == NULL || read_byte == NULL || latest_snapshot == NULL) {
        return 0U;
    }
    while ((byte = read_byte(context)) != PAGER_STREAM_NO_BYTE) {
        pager_snapshot_t parsed;
        if (push_byte(stream, byte, &parsed)) {
            *latest_snapshot = parsed;
            ++valid_count;
        }
    }
    return valid_count;
}
