# Display Pin Remap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remap the ST7789 signal pins to SCL=PB9, SDA=PB8, RES=PB7, DC=PB6, and BLK=PB5, then program a static RGB diagnostic build.

**Architecture:** Keep the existing software SPI and color-bar diagnostic paths. Only the GPIO pin constants change; power remains GND and 3.3V. Automated source tests lock the mapping before the firmware is rebuilt and programmed.

**Tech Stack:** STM32F103 HAL, C, GNU Arm Embedded Toolchain, pytest, STM32CubeProgrammer

## Global Constraints

- ST7789 GND connects to STM32 GND and VCC connects to STM32 3.3V.
- Use software SPI because PB9/PB8 are not a hardware SPI clock/data pair.
- Keep static red, green, and blue bars enabled until visual hardware verification succeeds.

---

### Task 1: Remap And Program The Display

**Files:**
- Modify: `tools/test_display_transport.py`
- Modify: `Core/Src/oled.c`

**Interfaces:**
- Consumes: Existing `LCD_*_PIN` constants and software SPI transport.
- Produces: Firmware using PB9/PB8/PB7/PB6/PB5 for SCL/SDA/RES/DC/BLK.

- [ ] **Step 1: Write the failing pin-map test**

```python
def test_display_signal_pins_use_pb5_to_pb9_mapping():
    assert "#define LCD_SCL_PIN GPIO_PIN_9" in SOURCE
    assert "#define LCD_SDA_PIN GPIO_PIN_8" in SOURCE
    assert "#define LCD_RES_PIN GPIO_PIN_7" in SOURCE
    assert "#define LCD_DC_PIN GPIO_PIN_6" in SOURCE
    assert "#define LCD_BLK_PIN GPIO_PIN_5" in SOURCE
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest -q tools/test_display_transport.py -k pb5_to_pb9`

Expected: FAIL because the current constants still reference PB13/PB15/PB14/PB12/PB1.

- [ ] **Step 3: Change the display pin constants**

```c
#define LCD_SCL_PIN GPIO_PIN_9
#define LCD_SDA_PIN GPIO_PIN_8
#define LCD_RES_PIN GPIO_PIN_7
#define LCD_DC_PIN GPIO_PIN_6
#define LCD_BLK_PIN GPIO_PIN_5
```

- [ ] **Step 4: Run tests and build**

Run: `python -m pytest -q tools/test_display_transport.py tools/test_blossom_asset.py tools/test_pager_state.py`

Expected: all tests pass.

Run: `make -j4`

Expected: build completes and creates `build/codex_usb_pager.hex`.

- [ ] **Step 5: Program and verify the MCU**

Run: `STM32_Programmer_CLI.exe -c port=SWD -w build/codex_usb_pager.hex -v -rst`

Expected: `Download verified successfully` followed by an MCU reset.

- [ ] **Step 6: Commit the implementation**

```bash
git add codex_usb_pager/Core/Src/oled.c codex_usb_pager/tools/test_display_transport.py codex_usb_pager/docs/superpowers/plans/2026-07-16-display-pin-remap.md
git commit -m "fix: remap display signals to pb5-pb9"
```
