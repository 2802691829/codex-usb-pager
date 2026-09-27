# Codex Pager: RP2040-Zero Porting Guide

This directory freezes the working STM32 pager design so it can be ported to an
RP2040-Zero without rediscovering the protocol, animation, or asset pipeline.
The STM32 implementation remains the behavioral reference.

## Current Status

The RP2040-Zero now drives the ST7789 through the verified PIO/DMA path. USB
CDC, the onboard WS2812 on GP16, and the optional active-low buzzer on GP14
remain active.

The temporary status effects are:

- `IDLE`: low cool white.
- `RUNNING`: blue-purple breathing.
- Multi-task running: the purple foreground Blossom continues uninterrupted;
  each additional task adds one complete, translucent blue/violet/cyan Blossom
  behind it, capped at three ghosts.
- `WAIT`: amber double flash.
- `DONE`: soft green pop every three seconds.
- `ERROR`: red triple flash and five short buzzer pulses.
- `OFFLINE`: dim red slow flash after eight seconds without a valid snapshot.

Every RGB channel is clamped to 20 out of 255.

## Frozen Behavior

- Display: ST7789, 240x240, RGB565, seven-pin SPI module.
- States: `IDLE`, `RUNNING`, multi-task running, `WAIT`, `DONE`, `ERROR`, and
  `OFFLINE`.
- Fixed visual center: `(120, 109)`.
- Animated region: `(34, 23)`, size `172x172`.
- Footer begins at y=196.
- Frame target: 72 ms.
- State transition: 260 ms exit followed by 480 ms enter.
- Running cycle: 4.7 seconds with continuous angular acceleration and scale.
- Multi-task cycle: 4.6 seconds plus three translucent colored Blossom layers.
- DONE has no check badge. Its pearl Blossom and mint ring pulse every 3 seconds.
- The active-low buzzer is non-blocking: 25 ms on and 180 ms between beeps.
- Host timeout: 8 seconds, then `OFFLINE`.

The exact animation and palette implementation is in
`../../Core/Src/oled.c`. Do not redraw the logo from primitives.

## Proposed RP2040-Zero Wiring

| Display/module pin | RP2040-Zero | Purpose |
| --- | --- | --- |
| GND | GND | Common ground |
| VCC | 3V3 | ST7789 power |
| SCL | GP12 | PIO SPI clock |
| SDA | GP11 | SPI1 TX |
| RES | GP10 | Display reset |
| DC | GP9 | Command/data |
| BLK | GP8 | Backlight, high=on |
| Buzzer IO | GP14 | Active-low buzzer input |
| Buzzer VCC | 3V3 | Buzzer module power |
| Buzzer GND | GND | Common ground |

The bare two-pin passive buzzer is not part of this saved design.

## USB Wire Protocol

The device receives newline-terminated ASCII over USB CDC:

```text
STATE <state> RUN=<n> WAIT=<n> DONE=<n> BAL=<token> EV=<event>\n
```

Example:

```text
STATE RUNNING RUN=3 WAIT=0 DONE=14 BAL=82 EV=NONE
```

Rules:

- `WAIT` has visual priority over running tasks.
- `RUNNING` with `RUN>1` selects the multi-task animation.
- `EV=WAIT`, `EV=DONE`, and `EV=ERROR` trigger 3, 1, and 5 quiet short pulses
  respectively. The boot pulse is one short pulse. RUNNING and multi-task
  running stay silent.
- Events are edge notifications; heartbeat snapshots normally use `EV=NONE`.
- Existing host aggregation remains in `../../tools/`.

## Files To Reuse

| Source | RP2040 use |
| --- | --- |
| `../../assets/openai-blossom.svg` | Canonical official Blossom source |
| `../../tools/generate_blossom_asset.py` | Regenerate the packed mask and sine table |
| `../../Core/Inc/blossom_asset.h` | Copy unchanged |
| `../../Core/Src/blossom_asset.c` | Copy unchanged; 8192-byte 4-bit alpha mask |
| `../../Core/Src/oled.c` | Behavioral reference for palette, animation, and compositing |
| `../../Core/Src/main.c` | Behavioral reference for parsing, timeout, and buzzer scheduling |
| `../../tools/pager_state.py` | Host state aggregation |
| `../../tools/pager_runtime.py` | Multi-task runtime database |
| `../../tools/pager_daemon.py` | Two-second heartbeat sender |

## Recommended Pico SDK Architecture

Use Pico SDK C/C++ with TinyUSB enabled.

1. Core 0 owns TinyUSB CDC, command parsing, the 8-second host timeout, and the
   non-blocking buzzer state machine.
2. The display renderer may remain on core 0 initially. Move it to core 1 only
   if USB servicing becomes uneven during full-frame animation.
3. Use a PIO state machine plus DMA for ST7789 output because the required
   consecutive GP29/GP28 wiring is not a fixed hardware SPI SCK/TX pair.
4. Render one 172-pixel RGB565 scanline into a 344-byte buffer. Use two line
   buffers and DMA so the next line can be composed while the previous line is
   transmitted.
5. Keep all animation calculations integer-only. Reuse `g_sin_q15[256]`, Q12
   scale, 8-bit angle, RGB565 blending, and 4-bit bilinear mask sampling.
6. Call `tud_task()` frequently. Accumulate CDC bytes until newline, then pass
   one complete line to the existing parser logic.

## Porting Boundaries

Preserve these functions conceptually:

```text
ui_init()
ui_set_dashboard(state, run, wait, done, balance)
ui_update(time_ms)
buzzer_start(count)
buzzer_update(time_ms)
process_line(ascii_line)
```

Replace only these STM32-specific pieces:

- `HAL_GetTick()` -> `to_ms_since_boot(get_absolute_time())`
- GPIO BSRR writes -> Pico GPIO helpers or SPI peripheral output
- software SPI and `set_window()` transport -> Pico PIO + DMA
- STM32 USB device stack -> TinyUSB CDC
- STM32 startup, linker script, HAL, and Cube USB files -> Pico SDK CMake target

## Host Discovery Change

`../../tools/send_pager.py` discovers both the Pico SDK RP2040 CDC identity
`2E8A:000A` and the STM32 reference identity `0483:5740`. The RP2040 firmware
uses the product string `Codex Pager`; `--port COMx` remains available.

## Stage 1 Build

Required tools are Pico SDK 2.2.0, ARM GNU Toolchain 14.3, CMake, NMake, and
picotool 2.2.0 or another picotool compatible with SDK requirement 2.1.1.

On this Windows machine, the ARM linker cannot consume object paths containing
Chinese characters. Build through an ASCII source path and keep the SDK and
build directory on an ASCII path. The verified target is:

```text
PICO_BOARD=pico
firmware target: codex_pager_rp2040
UF2: build-rp2040/codex_pager_rp2040.uf2
```

Native core tests:

```powershell
cmake -S ports/rp2040-zero/tests -B <ascii-build-dir> -G "NMake Makefiles"
cmake --build <ascii-build-dir>
ctest --test-dir <ascii-build-dir> --output-on-failure
```

Firmware configuration follows the same pattern with
`ports/rp2040-zero/firmware`, `PICO_SDK_PATH`, `PICO_TOOLCHAIN_PATH`,
`PICO_BOARD=pico`, and `picotool_DIR` set explicitly.

The verified local build helper stages the source and SDK under an ASCII-only
temporary path before compiling, then copies the UF2 back into the project:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1
```

## Acceptance Checklist

- ST7789 initializes at 240x240 with correct orientation and RGB order.
- Blossom bounding box is centered on `(120, 109)` at zero rotation.
- Rotation does not change the center pixel or create a visible jump.
- Single-task running completes a smooth 4.7-second cycle.
- `RUN=3` shows three translucent ghost Blossoms behind the primary Blossom.
- WAIT has three short low-level buzzer pulses without freezing animation.
- DONE contains no check and pulses at 0, 3, 6 seconds.
- State transitions last 650 ms and never clear to a bright frame.
- USB remains responsive while animation is active.
- Missing heartbeat produces OFFLINE after 8 seconds.
- The existing Python state/runtime tests still pass.

## Prompt For A Future Codex Session

```text
Read codex_usb_pager/ports/rp2040-zero/README.md and port_manifest.json.
Continue from the tested stage-1 Pico SDK firmware. Reuse blossom_asset.c/h and
the host wire protocol. Keep ST7789 output on BLK=GP8, DC=GP9, RES=GP10,
SDA=GP11, SCL=GP12 with packed whole-region PIO/DMA output, then add the
non-blocking active-low buzzer on GP14. Build and test before flashing. Do not
redesign the visuals.
```
