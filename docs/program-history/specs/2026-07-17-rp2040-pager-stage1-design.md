# RP2040 Pager Stage 1 Design

## Goal

Bring up the RP2040-Zero as the new Codex pager core using USB CDC and its onboard WS2812 status LED before the replacement ST7789 display arrives.

## Hardware

- Controller: RP2040-Zero with 264 KB SRAM and 2 MB flash.
- Onboard status LED: WS2812 data input on GP16.
- Maximum LED brightness: 8 percent.
- Buzzer reserved for stage 1 follow-up: active low three-pin module, IO on GP14, VCC on 3V3, and common GND.
- No display or buzzer is connected during the initial USB and LED bring-up.

## Future Display Pinout

The replacement seven-pin ST7789 display will use the physically sequential left-side pads:

| ST7789 | RP2040-Zero |
| --- | --- |
| GND | GND |
| VCC | 3V3 |
| SCL | GP29 |
| SDA | GP28 |
| RES | GP27 |
| DC | GP26 |
| BLK | GP15 |

GP29 and GP28 will use a PIO state machine with DMA rather than a fixed-function SPI peripheral. Display implementation is outside stage 1.

## Firmware Architecture

- Build with the Raspberry Pi Pico SDK in C/C++.
- Expose a USB CDC serial interface compatible with the existing line-oriented pager protocol.
- Parse complete newline-terminated snapshots without blocking the animation loop.
- Keep the most recent valid snapshot and transition to OFFLINE after the existing host timeout.
- Drive the single WS2812 from a dedicated PIO state machine on GP16.
- Run stage 1 on one core. Reserve multicore rendering and display DMA for the display stage.

## State Behavior

| State | LED behavior | Buzzer behavior after follow-up |
| --- | --- | --- |
| IDLE | Low-brightness cool white | Silent |
| RUNNING | Smooth blue-purple breathing | Silent |
| MULTI | Alternating blue and purple | Silent |
| WAIT | Amber double flash | Two very short pulses |
| DONE | Soft green pop | One very short pulse |
| ERROR | Red triple flash | Three very short pulses |
| OFFLINE | Dim red slow flash | Silent |

All LED effects use a perceptual brightness curve and never exceed 8 percent output.

## Protocol Compatibility

Stage 1 accepts the existing snapshot format, including state, running count, waiting count, completed count, balance, and event fields. Multiple running tasks select MULTI. Unknown or malformed lines do not replace the last valid state.

## Verification

1. Unit tests cover parsing, state selection, timeout behavior, and LED effect bounds.
2. The Pico SDK build produces a UF2 image for RP2040.
3. Copying the UF2 to RPI-RP2 reboots the board as a USB CDC device.
4. A host smoke test sends IDLE, RUNNING, MULTI, WAIT, DONE, ERROR, and OFFLINE snapshots and verifies the corresponding onboard LED behavior.
5. Stage 1 is accepted before any display or buzzer wiring is added.
