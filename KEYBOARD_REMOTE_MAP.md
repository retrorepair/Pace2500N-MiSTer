# Pace Guide keyboard / RP2040 remote mapping

Configure the RP2040 as a USB keyboard and assign the keys below in its PC app.
Normal key press/release events are supported. No special USB driver or serial
protocol is needed. The core translates these keys into the Pace firmware's
serial remote-control messages.

| Remote button | Keyboard key |
|---|---|
| TV Guide | F1 |
| Box Office | F2 |
| Services | F3 |
| Interactive | F4 |
| Sky / return to TV | F5 or S |
| Information | F6 or I |
| Help | F7 or H |
| Text | F8 or T |
| Standby | F9 or P |
| TV | F10 |
| Up / Down / Left / Right | Arrow keys |
| Select | Enter (main or keypad) |
| Back Up | Escape or Backspace |
| Channel + / Channel - | Page Up / Page Down |
| Red / Green / Yellow / Blue | R / G / Y / B |
| 0–9 | Top-row 0–9 |
| Play / Pause / Stop / Record | Space / J / K / C |
| Rewind / Fast Forward | [ / ] |
| MiSTer menu | F12 (reserved) |
| Fixed Teletext page 100 test (V080A/B) | F11; starts/cancels a 30-second diagnostic |

The current `cold-boot` branch (V080B) starts the original firmware in FPGA
logic using FLASH_U202.bin and the EEPROM save. Its Live launcher does not load
RAM.bin or STATE.bin. The PC supplies listings, media and live Teletext through
the relay; firmware execution stays in FPGA. Use **Pace2500N_V080B_Live.mgl**
in Other to start it. Earlier checkpoint launchers are historical builds.

For live Teletext, use the **TV's own Text and page-number controls**. Page 101
has a changing clock; 888 carries available subtitles. F8/T sends the Pace
firmware's Text command; F11 selects the separate fixed output test and
temporarily pauses live Teletext for up to 30 seconds. See
[LIVE_TELETEXT.md](LIVE_TELETEXT.md) for pages, setup and current validation.

Some remote functions require hardware features that remain unimplemented;
mapping a button alone does not establish that its native workflow works.

Machine-readable firmware-button mappings: `re/KEYBOARD_REMOTE_MAP.csv`.
F11 is handled separately by the core. PS/2 values in that
file describe MiSTer's internal Set2 event format; enter the **keyboard key
names** above in the RP2040 application.
