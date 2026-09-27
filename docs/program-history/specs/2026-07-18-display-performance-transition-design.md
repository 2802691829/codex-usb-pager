# RP2040 Display Performance And Transition Design

## Goal

Raise the 172 x 172 animated scene from its current visibly low frame rate to a stable 35-40 FPS where hardware permits, while replacing abrupt state changes with a 650 ms continuous transition. The implementation must preserve prompt-state responsiveness and the verified ST7789 panel profile.

## Rendering And Transport

The existing PIO program consumes one 32-bit FIFO word for every display byte and the driver configures DMA once per row. The replacement PIO program consumes all 32 bits of each FIFO word, so one word carries four consecutive display bytes. Each rendered RGB565 pixel pair is packed in panel byte order and the entire animation region is submitted by one DMA operation.

The scene renderer will remove integer division from the per-pixel dynamic-background path. Frame pacing targets 25 ms. If a frame takes longer, the next frame starts immediately without accumulating timing debt, yielding a natural 30-40 FPS range instead of duplicated or skipped animation time.

## State Transition

Changing state must not call a full-screen fill. The UI keeps the outgoing rendered frame and renders the incoming state into a second frame buffer. For 650 ms it blends outgoing and incoming pixels with a smoothstep curve. The incoming scene advances normally during the blend, so rotation and ambient motion never pause. After the transition, the outgoing buffer becomes reusable.

The transition applies to every state pair, including RUNNING, MULTI, WAIT, DONE, IDLE, ERROR, and OFFLINE. USB state selection and event priority remain unchanged.

## Memory And Safety

Two packed 172 x 172 RGB565 buffers consume 118,336 bytes. This fits within the RP2040's 264 KB SRAM while leaving space for code data, USB, stacks, and PIO/DMA state. A link-time size check and firmware build verify the remaining margin.

SPI remains at the already verified 24 MHz. Raising it is unnecessary until renderer and DMA overhead are removed, and avoiding that change keeps signal integrity stable on the hand-wired display.

## Local Test Environment

The inaccessible `.pytest-*` directories were created with unusable ACLs. Reset their ownership/ACL, remove only those known temporary directories, and configure pytest to use a single ASCII-only writable base directory outside the source tree. This prevents Git traversal warnings and Chinese-path pytest temporary-directory failures.

## Verification

- Host tests cover 25 ms pacing, transition duration/easing endpoints, frame packing order, and existing scene behavior.
- A host benchmark reports scene-render duration before firmware flashing.
- The RP2040 firmware build must succeed and report SRAM usage below the device limit.
- Flash the UF2 and verify RUNNING animation, RUNNING-to-DONE, and DONE-to-IDLE transitions on the physical panel.

