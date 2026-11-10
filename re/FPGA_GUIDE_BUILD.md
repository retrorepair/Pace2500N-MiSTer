# v047 FPGA Guide checkpoint build

User chose FPGA-only execution, then explicitly prioritized build and deployment.
No ARM/software CPU is used by this design. This is a disclosed checkpoint
resume, retaining the two diagnostic RAM interventions documented in
GUIDE_DIAGNOSTIC_CHECKPOINT.md. Protected-loader cold boot remains unsolved.

Build: builds/v047_guide, output_files/Pace2500N.rbf.
Current compile log: compile_v047_guide_b.log. First compile failed EEPROM
block-RAM inference; explicit registered read ports corrected it. Second
Analysis & Synthesis passed at20:20:34 UTC. Fitting currently running.

FPGA modules: checkpoint-capable CPU, native timer/serial/I2C/EEPROM/no-RF
models, DMA12 packed copy/fills, guest display-list/CLUT scanout, keyboard map.
Simulated100k instructions match GPR/CP0/PC against software. Simulated Select
through native serial RX completes21 graphics commands; full indexed frame
SHA256 be2a780ab6ad47144d62b90a59ce9f00e77d026a7310c5d28735334a2e1b6e42
exactly matches software All Channels output. All45 keyboard make/break mappings
pass. sim/guide_key_select.log records the10M-instruction run.

Assets re/fpga_guide_checkpoint/RAM.bin, STATE.bin and manifest exported by
 tools/export_fpga_checkpoint.py. RAM and state already staged/hashed on MiSTer
at /media/fat/games/Pace2500N_GUIDE/. Original U202 reused at
/media/fat/games/Pace2500N/FLASH_U202.bin. MGL local Pace2500N_Guide.mgl.
Keyboard map: KEYBOARD_REMOTE_MAP.md and re/KEYBOARD_REMOTE_MAP.csv.

SSH: root@192.168.1.103 with -o BatchMode=yes -o HostKeyAlias=MiSTer.
Server key was checked against the existing known MiSTer ed25519 key.
Fallback v044 /media/fat/_Other/Pace2500N.rbf and v046 EXP unchanged.
Pending deployment target: /media/fat/_Other/Pace2500N_GUIDE.rbf, followed
by MGL load via /dev/MiSTer_cmd. UART telemetry115200 /dev/ttyS1.
Guide telemetry repurposes mmio_address as GPU completions/acks (16bits each),
mmio_value as keyboard events/frames, mmio_read as last key/scanout underruns.
Native input smoke tool /tmp/pace_test_keyboard.py uses uinput only, not guest
RAM or CPU edits. It is staged but has not been executed yet.

No physical Guide screenshot or successful deployment is claimed yet.

## First hardware pass and correction in progress

First RBF built successfully,57%ALMs,258RAM blocks,66DSP, but setup slack
-1.339ns (actual palette conversion path, not the CPU). SHA256
c368e76e05d92ec3d52c7ab0108b0ccb1105e9f5e529b5ac8b65fec0d610ece5.
Deployed and loaded via MGL; real FPGA CPU advances from200M with IRQs.
SSH screenshot re/deployment/v047_guide_initial.png shows the genuine Guide,
but left-edge scanout underruns blank part of each line. Fetch scheduling
changed from last active pixel to first active pixel of preceding scanline.
Palette DDR capture was pipelined and arithmetic narrowed to correct timing.

Extended hardware run halted05 at80024FAC. Native pool80024FD8 holdsB4180000,
the known external output latch, previously handled by software but omitted
from FPGA address decode. Byte writes are now routed to peripheral output
handling. No firmware RAM/PC fix is used for this runtime correction.

Current replacement compile: compile_v047_guide_d.log, session38936.
Source root and builds/v047_guide now both contain fixes. Failed/cancelled
intermediate log_c is not the final build. Pending final RBF will replace
same _Other/Pace2500N_GUIDE.rbf and re-load same MGL. Do not claim it verified
yet. Native long idle simulation session51076 targets270M after latch fix,
log sim/guide_long_idle_fixed.log. Python270M control completed alive.

Input smoke test was sent before checkpoint finished loading in one run;
another was sent after the missing-latch halt. Thus keyboard hardware make/
break count was seen, but no successful live firmware key navigation proof
yet. Test after UART first reports RET>=200M, before waiting for prolonged
startup. tools/mister_test_keyboard.py is on MiSTer /tmp/pace_test_keyboard.py.

## Final deployment verified —21:25 UTC

Replacement compile_d completed successfully, all reported timing slack positive.
Core setup+1.279ns, minimum setup+0.218ns.23,778ALMs(57%),258RAM blocks(47%),
50DSP blocks(45%). Final RBF SHA256
771f2fa034d85039df97e2cdd7d32d93ebb0e228de986f967dd1b905d9dfb659.
It replaced the first test RBF and is loaded on MiSTer. Native CPU runs beyond
300M instructions, HALT00, IRQs increasing. Earlier B4180000 fault is passed.

Keyboard Down/Up through Linux uinput -> normal Main/hps_io path yields4key
make/break events,2remote frames,4new DMA completions/4acks. Guest rendering
returns to original Guide menu exactly. Both field buffers read back from
FPGA DDR have indexed SHA74695ee3962f14a3eea468e1703b70e121034a2020e4dffa948f05f09f375423.
Actual SSH screenshot v047_guide_fixed.png matches all640x576 expected pixels
within2LSB YUV conversion rounding; zero mismatched pixels. An apparent right
crop in the image preview was a mistaken visual interpretation, disproved by
this full-frame comparison. Scanout underrun count remains2 from startup,
not rising during normal display. Diagnostic readback renderer metadata is
explicitly marked hardware RAM readback, separate from actual SSH screenshot.

Final evidence summary: re/deployment/v047_guide_verified.json.
Core remains a two-RAM-intervention checkpoint diagnostic, no RF/listings,
not a protected-loader cold boot. HPS loads files and handles normal USB;
all firmware instructions/peripheral behavior/rendering execute in FPGA.
