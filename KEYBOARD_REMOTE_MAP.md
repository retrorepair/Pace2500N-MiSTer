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

The initial Guide build resumes a disclosed diagnostic firmware checkpoint.
It executes firmware in FPGA logic; it does not run a software CPU on the ARM
or require a PC connection. The loader handoff remains unresolved, and no RF
or broadcast listings are supplied. Some remote functions require hardware
features that are still unimplemented; mapping a button does not establish
that those features work.

The first build's reboot entry is **Pace2500N_Guide.mgl** in Other. It loads
the original U202, guest RAM and CPU checkpoint. Reload that entry to restart.
The ordinary v044/v046 cores are retained separately.

Machine-readable mappings: `re/KEYBOARD_REMOTE_MAP.csv`. PS/2 values in that
file describe MiSTer's internal Set2 event format; enter the **keyboard key
names** above in the RP2040 application.
