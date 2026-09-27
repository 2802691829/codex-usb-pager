# Display Pin Remap Design

## Goal

Move the ST7789 control signals to a compact PB5-PB9 group so the screen wiring can be resoldered cleanly and tested independently from the animation renderer.

## Wiring

| ST7789 pin | STM32F103 pin |
| --- | --- |
| GND | GND |
| VCC | 3.3V |
| SCL | PB9 |
| SDA | PB8 |
| RES | PB7 |
| DC | PB6 |
| BLK | PB5 |

## Transport

PB9 and PB8 are not an STM32F103 hardware SPI clock/data pair. The diagnostic firmware therefore uses software SPI. It starts at the established low diagnostic rate so wiring and display initialization are tested before performance tuning.

## Diagnostic Behavior

After reset, the display initializes and shows three static horizontal bars: red, green, and blue. Codex state rendering remains disabled during this test. A successful result is three stable colored bars with no black screen.

## Verification

1. Automated tests assert the pin mapping and diagnostic transport configuration.
2. The firmware builds without errors.
3. STM32CubeProgrammer verifies the programmed image.
4. The user visually confirms the RGB bars before animation rendering is restored.
