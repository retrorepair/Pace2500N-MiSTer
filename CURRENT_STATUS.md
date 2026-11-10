# Pace 2500N current status — 9 November 2026## Session 4 (10 Nov) - instruction timebase, I-cache, BT.601 video

Root cause of the listings abort (from Session 3 evidence): the model gave the
firmware ~25K instructions per 10 ms tick instead of ~810K. Firmware facts:
EMMA timer reload 810000 and CP0 Compare reload 202500 (= 810000/4) are the
same Nucleus tick, so the timer clock is 81 MHz (3 x 27 MHz) and Count is
timer/4. NEC rates the uPD6103x CPU at 66-100 MIPS. The old model used 32
timer counts and 8 Count per retired instruction, i.e. a 2.5-MIPS CPU in guest
time, so periodic CA work (ECM task posting 8000/8001 every ~0.5 s) outran the
UI task until its message pool was exhausted and it aborted (code 4C11).

Changes (source root `rtl/`, isolated builds `builds/v049_timebase`,
`builds/v050_video`):
- `pace_guide_peripherals.sv`: TIMER_COUNTS_PER_INSTRUCTION=1 (instruction-
  domain timebase; documented in the code as a platform workaround because the
  FPGA CPU retires ~2.5M instr/s). Guest time now runs ~33x slower than wall
  time on hardware; timer-driven UI waits are correspondingly longer.
- `pace_firmware_cpu.sv`: CP0 Count increments once per 4 retired instructions
  (Count = timer/4). New ICACHE parameter: 16 KiB direct-mapped KSEG0 I-cache
  (16-byte lines, valid per 8-byte DDR word), CPU-store and CACHE-op
  invalidation, flush on reset/checkpoint load. D-cache ops remain no-ops.
- Verified: cache on/off from the 200M checkpoint to 215M (NO_TS) gives
  bit-identical guest RAM and CPU state; 99.98% hit rate in that window.
- Horizontal scaling: `pace_guide_video` sampled the 720-pixel OSD at 640
  samples (`x + x/8`), dropping every ninth column. New `pace_pal576i601.sv`
  (54 MHz / 4 = 13.5 MHz, 864 samples/line, 720 active, BT.601 blanking) and
  dual-clock `pace_guide_video601.sv`. `sim/tb_guide_video601.sv` passes:
  622,080 pixels exact 1:1 over 3 fields, async 50/54 MHz, no underruns.
  PLL gains a 54 MHz output; `Pace2500N.sdc` marks the two outputs async.

v049 (timebase + I-cache only) on hardware, `_Other/Pace2500N_V049.rbf`, SHA256
fa7cedab...83bd8fc: 5.78M instr/s (was 2.47M), 31 IRQ/s, Guide menu and
Select -> ALL CHANNELS / Searching for listings render promptly. Timing: core
setup +0.887 ns, hold +0.218 ns; MiSTer's HDMI PLL path -0.007 ns (framework,
not CRT). 76% ALMs, 402 RAM blocks.

But after 6 minutes the message pool was again exhausted (free 0, 270 to
TASK30) with the CPU idle, so starvation was not the whole story. Tracing:
the CA task posts 8001/8000 every 2 ticks because the smartcard ISR
(800F2F88) reads event status B000B814 = 0x04 and requests card activation
(command 2 at 80141DAC); activation (800F3398) gets no ATR and clears the
event by writing 4 to B814. Plain-storage CSRs read that 4 back as a new
event. B814 is now write-one-to-clear (`pace_guide_peripherals.sv`); with no
card nothing sets it. Sim: one activation from the stale checkpoint value,
then silence (vs ~7 pairs per 12M instructions before).

v050 = timebase + I-cache + smartcard W1C + BT.601 video. Seed 2 failed
routing (hold-fix congestion, 69% ALMs); seeds 3 then 1 are being tried
(`builds/v050_seed3`, `builds/v050_seed1`).

Background music (requested 10 Nov): firmware has Sound Settings
"Background Music", HISRAUDIO_MP, AUDIO_MPEG and AUDRAM; driver uses the
B0002xxx A/V block and the 13-channel DMA engine (FUN_80005900). No B0002
accesses occur in 30M instructions after Select with the current synthetic SI.
Selection of the music service by the OpenTV Guide is not yet traced.

v050 deployed (seed 3; core +1.720 ns, video +4.061 ns, hold +0.248 ns;
MiSTer HDMI scaler `ascal` -0.107 ns). 6-minute soak: message pool 270 free
(was 0 on v049). Screenshot 720x576 matches the guest framebuffer exactly.

Regression found by the user: listing-row bars and a clipped heading behind
the ALL CHANNELS dialog on v049/v050, absent on v048 and in the software
reference. Cause, proven in simulation: the Guide copies text via DMA 00AC
from one source buffer at 0x55C288 that the CPU refills through KSEG1
(uncached, loop at 80000E4C called from 800847E5) while the previous copy is
in flight. Real uncached VR4110 stores are slow bus transactions and the
EMMA DMA is fast, so the firmware never sees the overlap. The model's blitter
did one DDR write per pixel; with the I-cache the CPU overtook it (19,002
writes ahead of the copy position vs 0 without the cache). The firmware
issues CACHE 0x19 (Hit Writeback D) only for the 80108C40 display list.
- `pace_guide_blitter.sv` now merges pixels into 64-bit word writes and reads
  each source word once. Cache off + word blitter: frame identical to the
  clean reference (0 index pixels differ). Cache on + word blitter: heading
  fixed, bars remain, so the blitter must also burst-read before the I-cache
  can return.
- v051 = v050 with ICACHE=0 and the word blitter: all timing positive (core
  +1.876, video +4.550, HDMI +0.223, hold +0.255 ns). Hardware: the screen
  behind the dialog is clean again.

Next CPU-speed step: burst DDR reads in the blitter (DDRAM_BURSTCNT>1) so a
copy outruns the CPU's uncached refill, then re-enable ICACHE.

Broadcast clock (v052): `pace_tot_clock.sv` rewrites TOT (0x73, PID 0x14)
UTC_time from the MiSTer RTC (hps_io, BCD; MiSTer Linux syncs it from the
internet) and recomputes CRC32; OSD "Broadcast clock (TOT)" MiSTer RTC / TS
file. `sim/tb_tot_clock.sv`: 5/5 TOTs rewritten to MJD 61354 12:34:56 with
valid CRC, no other byte changed. Listings in the fixture are still dated
2002-09-01; the "time travel" year (OSD) is future work.

## Session 3 (9 Nov, evening) - investigation only, stopped early at user request

No RTL, ROM, MiSTer file or core was changed. Nothing was pushed to GitHub (no
repository exists yet; `gh` is logged in). Only additions: plusarg-gated
`+CATRACE` hooks in `sim/tb_guide_transport.sv`, read-only Ghidra scripts
`re/scripts/DecompileContaining.java`, `LinearM16.java`, `DecompileM16Auto.java`,
and evidence under `re/deployment/s3/`, `re/s3_*`, `re/transport/s3_catrace_*`.

Measured / verified:
- MiSTer is running **compile f**, not g. Process command line is
  `MiSTer _Other/Pace2500N_TS_DIAG.rbf _Other/Pace2500N_Transport_Sparse.mgl`;
  that file's SHA256 293f6309... equals `re/transport/build_f`. The MGL's
  `<rbf>_Other/Pace2500N_TS</rbf>` prefix-matches both RBFs. Morning "g"
  hardware evidence from the sparse launcher is therefore f evidence (same
  functional RTL, HDMI path -0.005ns). Fix: move/rename the DIAG RBF.
- Live sparse run: HALT00 but the guest has aborted. PC sits at 8003A938/3C,
  which Ghidra shows is the non-returning loop of 8003A928 (called after the
  abort), free messages 0, 270 queued to TASK30, a Guide key (00020008/0600)
  stuck in that queue. Screenshot `re/deployment/s3/resume.png` shows the
  frozen TEST ONE banner at 12.12pm. RAM capture and census alongside.
- FPGA CPU speed measured over UART: 2.47M instructions/s (about 20 clocks
  per instruction at 50MHz), 712 IRQ/s.
- Guest timer reload B000D050 is 810000 (checkpoint CSR), a literal in the
  firmware. NEC's product letter in `re/original_archives` states a 66-100
  MIPS CPU.
- The event8 (08000000, 8000/8001, sequence) messages are posted by the
  Nucleus task named **ECM** (stack 8012F2C0..801312AC), via 80051D18 ->
  8007FAA4 -> 8007FB08. Short trace `re/transport/s3_catrace_short_mmio.log`:
  about every 1.2M instructions a task with SP 8018D7xx sends 80000103 to the
  verifier queue 0; the ECM task then posts 8001 and 8000, followed by sends
  of 80001300 (queue 0), 80000701 and 80001403 (queue 1, EMM task).
- In the 650M simulation the producer sequence reached 2128 while TASK30 had
  consumed up to 1851: production rose about threefold after roughly 275M and
  then matched TASK30's consumption rate (about one per 181K instructions).

Inferences, not yet proven:
- 810000 suggests an 81MHz timer clock and a 10ms tick. The model's 32 timer
  counts per instruction then happens to give about 98 ticks/s at 2.47 MIPS,
  i.e. roughly real time on the FPGA, with a CPU some 27-40 times slower than
  NEC's figure. That would let periodic CA events outpace the UI task.
- Whether the flood is purely CPU starvation or also a missing smartcard/CA
  hardware response is undecided. `re/s3_ca_event_chain_decompile.txt` holds
  the Ghidra decompilation of the posting chain (800E8FC4, 800F0AA6, 800DFA5E,
  800DF9EE, 800E3DAA, 800E3A2A, 80038AFC); it was generated but **not read**.
  The longer `s3_catrace_long` run was killed before the post-lock phase; its
  partial log is incomplete.

Proposed next steps (none started): read that decompilation; if CPU-bound,
add a block-RAM cache in front of the CPU's DDR port and move the EMMA timer
to a real 81MHz-equivalent clock (the two must change together, otherwise
ticks speed up with the CPU); create the private GitHub repository, excluding
firmware dumps, RAM images, build trees and the GoRetroTv checkout.

## Transport handoff implementation - v048 deployed, listings under investigationThe attached streamer handoff has been reviewed and revised in`re/TRANSPORT_INTEGRATION.md`. Native FPGA TS replay and 32-channel sectionDMA/interrupts are implemented in isolated `builds/v048_transport`. Compile gpasses reported timing: core +1.204ns, minimum +0.096ns, 75% ALMs, 387 M10Ks,50 DSPs. RBF SHA256 is`4085c2a69c1986b274da9f0830ec29b1d4aa81064ea7d95398f0f9d6803148d7`.It is deployed separately as `_Other/Pace2500N_TS.rbf`. The v047 fallback ispreserved. Build/source/ROM evidence: `re/deployment/v048_build_verified.json`.The launcher now loads flash, RAM, TS, then CPU state. Restoring CPU statebefore the TS upload caused an intermittent HALT05: ordinary upload hold resetsthe CPU decode/branch state. State-last launch passes that point. Restart throughthe MGL to change TS files; runtime hot replacement is not yet supported safely.Actual MiSTer readback confirms the entire TS file in DDR and CRC-valid C1,A2/A3, TOT, SDT/BAT and NIT records in the guest rings. Enter reaches the normalkeyboard/remote path. Hardware captures progress from ALL CHANNELS/no signalto Searching for listings. No populated rows have been verified.Longer validation exposed a guest software abort despite HALT00. Ghidra and avalidated SDK message-list census show free buffers=0, 270 queued to TASK30;the send/retry path aborts with code4C11. The producer of the queued event8messages is under investigation. `Pace2500N_Transport_Sparse.mgl` is the currentrate diagnostic: 8-second replay, table wave every2s, one fixed TOT per file.The standard and versioned-index launchers are also retained. Native long-runtrace `sim/guide_long_test.log` traps at the original software-abort entry.Protocol RTL tests pass (1802 exact DMA bytes, CRC/loss/duplicate handling,ring-full/wrap, 32 paired match units, wrong-table rejection, shared PIDs,BE status). The original boot DMA/indexed-port software tests still pass.An early native delivery run reached280M and programmed title PID36/A3,IDs0BB8/0BB9, MJDCD26. Its actual writes exposed/corrected an erroneous16-unitinterpretation in the public reference before deployment. A fresh run usesthe corrected filters plus matching synthetic OpenTV titles/B2 rows.The native Huffman encoder derives the exact tree from operator RAM. Its outputpasses the original 800BECF0 decoder running on the actual FPGA CPU model.The original 800044BC ring-length helper independently passes all three headerboundary positions. DMA now wraps individual bytes. A registered MMIO responseand packet-alignment counter replace the timing failures found in compile c.The registered-bus/circular-ring native run reached 300M instructions, consumed461 sections and acknowledged all461, no halt. A no-transport keyboard controlpasses the original21 DMA Guide redraws. The data-fed late-key runs do notredraw the menu yet. The fresh early-key/versioned-index run consumes 601 sectionsand renders ALL CHANNELS with a no-signal dialog, without programme rows.The frontend has reached native state 7/flag 1. The saved application stackcontains NVRAM/service-list routines and the favourites-rebuild bytecode loop;a longer run is needed before treating this as a persistent GUI failure.See `re/TRANSPORT_UI_FOLLOWUP.md`. A native notification trace is running.Compile e failed routing congestion (80% nominal ALMs,96% occupied LABs).Filter rules now use one M10K, removing about4800 registers. Reset/clear/seedrestore and packet tests pass. Compile g is the deployed timing-passing image.The PC scheduled localmedia producer passes real FFmpeg encode/probe/decode; this does not add MPEGdecoders to the FPGA. No historical data or placeholder web media was downloaded.Launcher: `Pace2500N_Transport.mgl`, index 3 full-day SI/OpenTV replay, distinct`_Other/Pace2500N_TS.rbf`. Transport/input validation passes; application-levelmessage exhaustion remains a blocker to populated listings.Populated OpenTV listings and protected-loader cold boot are still unresolved.

## Latest hardware deployment — v047 Guide

Built, deployed and loaded FPGA-only Guide checkpoint core. Both CPU and the
runtime peripheral/graphics models are FPGA logic; no ARM software CPU.
Actual screenshot re/deployment/v047_guide_fixed.png and full guest-RAM
readback verify the native Guide menu. Down/Up produces4real DMA redraws;
CPU continues beyond300M with HALT00. Timing passes (core+1.279ns,
minimum setup+0.218ns). Load Other/Pace2500N_Guide.mgl. Keyboard/RP2040 mapping
is KEYBOARD_REMOTE_MAP.md (F1Guide, arrows, Enter, Escape, R/G/Y/B).
This resumes the disclosed200M diagnostic checkpoint with two RAM interventions;
protected-loader cold boot and RF/populated listings remain unresolved.
See re/FPGA_GUIDE_BUILD.md for final hash, corrections and evidence.

## Latest software RE checkpoint


**19:30 UTC: actual Guide menu pixels in the software diagnostic.**
Original firmware draws the complete ten-entry TV GUIDE category menu and
Select opens ALL CHANNELS / Searching for listings. See
`re/GUIDE_DIAGNOSTIC_CHECKPOINT.md` and the two exported PNGs. These are guest
framebuffer/CLUT exports, not MiSTer captures. Two explicit RAM interventions
(native AV default return and bound root readiness) remain necessary; reports
mark firmware_modified=true. No ROM file or FPGA build was changed.

New00AC0000 packed indexed copy writes actual CPU-rasterized source pixels.
A MIPS32 J/JAL delay-slot interrupt EPC/BD bug was fixed and replayed before
export; final menu snapshot200M has23/23 graphics completions/acks, All Channels
snapshot210M has44/44. Eight relevant checks pass. Same-ROM public GoRetroTv
reference at revisionfa3a471 corroborates the hardware facts and discloses its
own handoff/presentation interventions. The protected-loader handoff and
populated broadcast listings remain unresolved. Earlier "no Guide" entries
below are historical checkpoints, superseded only for this software diagnostic.



**18:54 UTC continuation:** Software reaches185M instructions, issues four
01AC0000 indexed rectangle commands, and fills two720x288 fields covering a
720x576 screen with native palette indexDC. Layout inferred from the original
rectangle builder, actual two-field allocations and four y-band coordinates;
not validated on hardware. Eight real DMA completions/acknowledgements match.
Snapshot indexfill_01 stops honestly at derivative frontend status APR001C.

Explicit --lsi-extended-status-zero control supplies no-RF zeros for driver-
accepted APR24..33 (unconfirmed silicon data), allowing frontend polling to end.
indexfill_02 reaches210M with main/UI tasks waiting on event queues. A Guide
keyCC is framed through real serial RX and decoded toCC/native0600; Sky80 and
a second Guide press also run through normal key handling. Latest snapshot
application_guide_key_02 at235M. Still only a uniform background; no Guide.

Ghidra tracing now follows OpenTV event delivery. Earlier tentative clock/vsync
labels were disproved:83E20 peeks UI events,84008 copies event data usingFBDE8
(memcpy, not memcmp), and84050 waits for an event. Control state80106CC4=2 is
'running'. Do not interpret those routines as a timebase or fabricate a clock
fix. Latest code is not in the14:16 archive. Hardware remains v046 EXP.


**18:16 UTC continuation:** Original firmware formatted the diagnostic erased
EEPROM and wrote/read back settings. A missing MIPS32 SWL in its unaligned
memset was implemented with LWL/LWR/SWR;36 independent Ghidra p-code cases pass,
including every alignment, paired accesses and delay slots. CPython/PyPy
100k-instruction CPU/RAM/peripheral differential also passes. Standalone PyPy
was extracted under /opt/pace-pypy for longer software traces; no unrelated
broken system packages were repaired.

At100M instructions, main TASK0 waited on STXD0. Ghidra2D4C0/2CCA0 and the
native interrupt table prove on-chip serial TX50/status60/enable70 atB2002000,
EMMA mask10000. New optional native_serial0 profile completes the guest's
queued600001110474 through6 real IRQs, releases its TX semaphore and supplies
no RX/card data. Application proceeds through timeout/failure paths.

B4080100..7 is another external byte-MMIO region, now classified as such;
its device protocol remains unknown and reads still use the explicitly unsafe
zero-MMIO experiment. This does not constitute validated emulation of that
part. By120M instructions more than30 tasks exist and EEPROM totals19453 reads,
3132 guest-written bytes. Longer continuation is active; still no Guide pixels.
Latest completed snapshot: re/application_serial0_02.pkl.gz. FPGA unchanged.


**14:48 UTC continuation (software only):** A separate functional, no-RF
LSI512-word profile now records the observed D5/D7 controls and shared grouped
register behavior without executing acquisition microcode or asserting lock.
It passes frontend initialization with no provisional flat-register seeds.
B4080000..7 is the external16550 UART (byte-lane XOR3), not a board strap;
its original driver now initializes divisor4, FIFO and line controls normally.

Original graphics DMA12 commands now fill actual guest luma/chroma buffers.
The genuine DMA ISR80005E28 acknowledges4/4 completions in
`re/application_graphics_03.json`. Native interrupt-table mapping is mask2,
not `1 << logical_irq`. The only implemented GPU packet is observed solid-fill
418F0000; unsupported packets stop. Buffers currently contain black/neutral
video initialization, not Guide pixels.

Next dependency: A0/A1 EEPROM. Absent-device control retries indefinitely;
Ghidra confirms two-byte big-endian internal addressing. Optional diagnostic
`--eeprom-blank` supplies erasedFF storage and retains guest writes. Capacity
64KiB and instant writes are explicit assumptions; no original EEPROM dump is
available. The guest now reads a16KiB settings block via its real I2C ISR.
Latest run is still being examined. No Sky Guide output observed.

All of this remains an **application-entry experiment**, not protected-loader
handoff or an FPGA update. Current hardware stays v046 EXP, with v044 fallback.
New graphics IRQ, fill, UART, grouped-control and EEPROM protocol checks pass,
as does the existing end-to-end I2C ACK/NACK regression.

New comparison reference: user supplied Drew1440's2500S5 teardown. It is an
STi5512/ST20 platform, but its close-up clearly shows a separatePIC16F74 at
U1200. Recorded as a possible peripheral/watchdog architecture comparison,
not evidence of the2500N's chip or protocol. See
`re/REFERENCE_2500S5_COMPARISON.md`. No model behavior changed from this lead.

**14:15 UTC checkpoint:** Strict application entry RE now captures the genuine
1024-byte frontend microprogram and stops at the next unsupported operation:
LSI-family group5 control APR0400=D5 (`application_lsi_strict_02.json`).
Program SHA256 `412837c684da392874a8d21e358d09baf51830e2bd6af915077abf8f18f1c094`.
The grouped interface matches the LSI family, but the public L64724 releaseB
manual has a smaller program/control map. Exact derivative remains unconfirmed;
L64734 documents are saved for comparison. This is an emulator stop on unknown
semantics, not evidence of a guest firmware failure. No microcontroller execution
or satellite lock is asserted.

Two optional **provisional flat-register** experiments seeded07 with00 andFF;
both reach board-input readB4080000 at16,265,787 instructions. These are controls
only: Ghidra shows the real device uses grouped/paged registers, so the strict
grouped profile supersedes their apparent progress. Do not deploy that flat model.

All relevant checks pass: extraction against actual MIPS startup, command53
builder, I2C ACK/NACK through genuine ISR/return codes0/8, application idle
differential, indexed demux helpers, DMA/CRC filters, exact CRC acceleration,
grouped APR behavior and actual microprogram upload. Hardware remains unchanged.

**Later continuation (~13:45 UTC):** User supplied the original archive source,
http://colibri.bplaced.net/firmware.htm. Fresh downloads of all three ZIPs verify
both supplied flash files and the separately published protected bootloader
byte-for-byte. The local-copy-only12614 routine is present in the original
publication. Archive manifest is under `re/original_archives/`.

The application is now available for independent RE: genuine startup decompresses
1,029,152 code bytes into RAM. All five initialized segments match a separate
extractor byte-for-byte. Ghidra project `re/ghidra/PaceAppRAM` maps that code plus
original flash aliases and uninitialized RAM. This is an **application-entry
experiment**, not observed protected-loader handoff.18M-instruction experiment
has687 IRQs and a main-task wait on frontend initialization. No firmware UI.

Ghidra identified an I2C completion wait. A driver-derived channel0 model now
uses the genuine IRQ/ISR path to complete the observedCA write `3f fe a6 70`;
NACK control ends it as an error. No I2C read data or demodulator lock supplied.
Later strict trace stops on address00; an explicit unknown-device NACK control
reaches20M instructions and is being examined. Exact scheduler idle acceleration
agrees with normal stepping for100k instructions. See
`re/APPLICATION_HANDOFF_INVESTIGATION.md`, tools/ and re/application_i2c_*.

Original JTAG manual's board drawing labels NEC D61032 and AT49LV1614 flash.
Added matching NOR ID001F/00C0 while preserving the older MBM profile for
reproduction. Fresh Atmel-profile loader run `re/boot_atmel_fresh.json` reaches
61M instructions, both valid images, same wait path, no application entry.
Exact physical alias decode and peripheral timings remain hypotheses. FPGA
is unchanged v046 EXP with v044 fallback.

**13:20 UTC continuation: software reaches valid application selection, but
does not enter the application.** The serial completion blocker is resolved:
reply opcode52 runs the genuine handler06408 and releases APeriph; generic
ACK10 does not. UART output, active-low front-panel inputs (FFFF released),
and an exact, optional CRC-loop accelerator let the unmodified loader validate
both supplied application images and print `1.2.7`, `01-1-45-0`, `02-1-45-0`,
`03-0`. See `re/application_boot_03.json` (100M interpreted instructions).

Ghidra identifies a new issue: selected-image path1284A calls12614, whose actual
ROM bytes only copy32 header bytes onto a local stack and return. Caller copies
the selected header to A0002000, then enters permanent wait036F8. No application
entry is observed. Investigating execution/provenance/reset contracts; no PC,
validation result, or firmware instruction has been patched. The two older
local project archives contain the same firmware hashes and same routine.
Original public archives exist as offline phone-storage placeholders; attempts
to read/copy them failed, so they have not provided independent provenance.

Current FPGA remains **v046 EXP**, with v044 fallback preserved. Demux, NOR,
serial replies, UART and later application investigations remain software only.
Peripheral timing/profile assumptions remain explicit; sequence enforcement is
not established. The earlier serial-blocker paragraph below is historical.

Both genuine boot hardware self-tests now pass in a fresh reset-to-boot run.
Guest-configured DMA/PSI demux generates bytes that the firmware compares and
accepts. The firmware itself writes boot flag800081F8=0 and takes normal path
9FC012E6, runs GPIO initialization and identifies an explicitly inferred NOR
profile. See **re/DEMUX_SELFTEST_PASSED.md** for evidence, commands and limits.

Next blocker is an external peripheral response, after genuine serial task
transmits03011107 then03024100 under a provisional clock/peer model. No reply
has been fabricated. Fresh run: re/demux_fresh_04.json + RAM/pickle; serial
capture: re/serial_peer_capture_02.json. Models/tests are under tools/.

Current FPGA remains **v046 EXP** (earlier timer-only hardware), with v044
fallback preserved. These later demux/NOR/serial changes are software only.
No application/Sky Guide boot is observed. Earlier entries below are history.

## Verified checkpoint: v0.4.4

The original U202 bootloader executes on the real DE10-Nano. The user supplied
a CRT photo showing the diagnostic monitor; SSH UART and an FPGA screenshot
confirm the same endpoint. This is early real-firmware execution, not Sky Guide.

- PC BFC01E1C, instruction AB616C01, MIPS16, HALT 03, read B0000012.
- 3,178,988 retired instructions; 1,770,706 RAM writes; 12 MMIO writes.
- All 2 MiB of uploaded flash in FPGA-reserved DDR match the genuine U202
  SHA-256 `32f6b2e84d0c4c4ec280a72f2d080e4b6fa5e68e8438ef712f34f97f63d38c7f`.
- Guest RAM pointers at 80008200 remain `b0000010b0000000` under live scanout.
- RBF SHA-256 `7fbefa9f53c9e6fdad98dd5ac467466ae473c89000235cf75e04793090f0104d`.
- Clean Quartus 17.0.2 Lite full build: 13 min 42 sec, 0 errors.
  13,680 / 41,910 ALMs (33%), 189 / 553 RAM blocks (34%).
  All reported timing checks pass; minimum slack 0.216 ns; no unconstrained clocks.
- `compile_v044_final.log`, `output_files/*.rpt` / `*.summary` are the reports.
- `re/deployment/uart_v044_verified.log`, `ddr_v044_verified.log`,
  `boot_monitor_v044.png`, and `crt_photo_20261107.jpg` are hardware evidence.

MiSTer is reachable as `root@MiSTer` using the existing SSH key (192.168.1.103).
The verified core is `/media/fat/_Other/Pace2500N.rbf`. The adjacent
`Pace2500N_FullFlash.mgl` loads the genuine image from `games/Pace2500N/`.
Global MiSTer.ini settings were preserved. Console is ttyS0; telemetry is ttyS1,
115200 8N1. Screenshot command: `screenshot <label>` via `/dev/MiSTer_cmd`.
The TV overscans the monitor edges but its central CPU data is readable.

## Important fixes already included

- Repaired stale simulation ports and checked all seven initial MMIO writes.
- Added a PLL-derived 50 MHz core/video clock, required by shell clock selects.
- Corrected MIPS16 LWPC/ADDIUPC bases, including jump-delay origins. The old
  Python/RTL pair shared a PC+4 error, hence the obsolete B0000002 trace.
- Moved guest RAM from physical 20000000 to 30000000 and flash from 22000000
  to 32000000. Old addresses collided with scaler buffers and Linux framebuffer
  (measured fb0 base 22001000, size 384000). v0.4.3 must not be used as current.
- Added UART snapshots, memory-lane/backpressure, strict boot, PC-relative,
  serial and PAL raster tests. Both project generators reproduce QSF offline
  from bundled `sys/` and `tools/mister_platform.qsf`; shell hashes recorded.
- Monitor caption now says 0.4.4. A quick MIF update gave an incomplete digital
  capture, initially misdiagnosed as a ROM failure. A clean build produced the
  identical RBF hash, and a fresh capture shows the full monitor. Archived
  experiment files under `re/caption_update_*` are not needed for normal builds.

## Active overnight work

User explicitly requested eight hours of continued work, **23:02:32 UTC on
7 Nov until 07:02:32 UTC on 8 Nov**. An active goal records that timebox.
See `OVERNIGHT_WORK_LOG.md`. Keep working until that deadline, preserving a
known-good checkpoint before changing the RTL. Do not infer that the task
ends merely because v0.4.4 is verified.

Current exploratory tool: `tools/pace_probe_research.py`, separate from the
checkpoint interpreter. It corrects MIPS16 memory register roles, shift fields,
NOT source, compact returns and implements EXTEND forms. Directed tests pass
in `tools/test_research_mips16.py`. Strict mode matches the hardware endpoint.
With explicitly experimental zero MMIO, it passes the former F140 blocker,
executes 545 extended instructions, and reaches a polling loop at BFC0B118:
B0009120 bit 0x20 must become set. Ghidra agrees with this loop. Register meaning
is not established. Reports: `re/research_zero_02.json`, `poll_9120_ghidra.txt`.

Next priorities: preserve/package v0.4.4, investigate that peripheral wait,
add independently tested MIPS16 decoder corrections and EXTEND to a new RTL
candidate, compare traces against software, then compile/deploy experimental
progress without presenting guessed MMIO as accurate hardware emulation.
The default hardware policy remains Halt. No fabricated Sky UI.

## Later candidate status — 8 November, 00:04 UTC

The active working RTL is now a **v046 source candidate**, not the deployed
v044. Frozen v045 and v046_exp builds are running under builds/. All ten
ModelSim suites pass. 260 independent Ghidra cases also pass the RTL; a 32-cycle
HI/LO unit passes 2,028 arithmetic cases. MIPS16 register roles, shifts, moves,
EXTEND, halfword boundary fetch, RAM execution, ERET and Count/Compare are added.
Experimental profile is explicitly zero MMIO plus B0009120=20. v046 UART frames
are 175 bytes and add IRQ/GUESS/POL; ordinary v044/v045 frames are 134 bytes.

Software 50M instructions reaches Nucleus scheduler idle with 1,831 timer IRQs
and real firmware tick0x725. BOOTMain waits forever on semaphore8000A820 via
9FC069F0. Investigate the device completion path; no application boot yet.
See OVERNIGHT_WORK_LOG.md and re/research_timed_09*. The verified default RBF
and immutable v044 archive remain intact. Deadline remains 07:02:32 UTC.

## Resumed deployment verification — 8 November, 07:27 UTC

The session was paused after the overnight build launches; it resumed after
07:20. Do not describe the intervening pause as continuous active RE work.
Both frozen builds completed successfully: v045 at00:11:34 (19m34), v046_exp
at00:19:30 (20m19), each0 errors/81 warnings. The full 8M-instruction RTL
research simulation passed at00:04:43: PC9FC0DE68, IRQ110, firmware tick0x6D.

**Current running hardware: v046 EXP** at /media/fat/_Other/Pace2500N_EXP.rbf.
SHA256 f8f3a9dbf4c00ff9e367bafd9a15f098d87e99db1d251c1e1a3595e90532b9d1.
18,316/41,910 ALMs(44%),189 RAM blocks(34%); reported timing positive,
minimum setup0.212ns and minimum observed hold0.243ns. Strict v044 default
RBF remains available and unchanged.

MiSTer now executes the real protected boot firmware into Nucleus scheduler
idle9FC0DE4C..68, with rising retire count and timer IRQs, HALT00, FLASH1,
policy1. This uses guessed zero MMIO +B0009120 bit5 and approximate50MHz Count.
Full2MiB DDR flash hash matches U202. RAM confirms increasing kernel tick
8000842C (0x23A3 then0x434C), empty ready queues, and BOOTMain TCB80013AE0
with saved wait routine9FC1117D and suspend record802AAC34, matching software.
The device completion/semaphore wait at9FC069F0/8000A820 remains the blocker.
No full application boot, firmware UI, or Sky Guide is observed.

Initial experimental MGL relative path failed because the core's game directory
Pace2500N_EXP did not exist; old DDR contents still matched and did not prove a
new upload. Using the absolute /media/fat/games/Pace2500N/FLASH_U202.bin path
fixed it: actual upload/reset seen, FLASH1, full DDR SHA verified again.
Temporary test f0 autoload config was removed. EXP MGL now uses absolute path.

Evidence: re/deployment/v046_exp_verified.log, scheduler_v046_exp_verified.log,
boot_monitor_v046_exp_fullflash.png. Both normal and accelerated 50M software
runs match all registers/CP0/PC, all16MiB RAM, interrupt events and ticks;
46,075,952 idle instructions safely skipped in the accelerated run.

### Rendering caveat found during final screenshot inspection

The pre-upload EXP screenshot has full monitor labels. Both post-full-flash
captures show live numeric columns but omit static text labels. UART remains
healthy, FLASH1, scheduler/tick data verified via read-only DDR mapping. Do not
claim complete post-upload monitor rendering or CRT confirmation. The same
kind of incomplete capture appeared earlier on v044 but its cause is still
unproven; here it repeats after upload and needs investigation. Static labels
are diagnostic ROM content, not genuine firmware UI. Current hardware CPU
progress is verified independently of this visual issue.

Sealed candidate archive: ../Pace2500N_v046_exp_sources_rbf.zip
SHA256 d0ac7838b88fa186d8208f33b3838e81768aff4c051e8f9c7e47f8093e6b37aa.
The archive predates this final rendering caveat; see its adjacent NOTES.md.

## Ghidra follow-up: original event/timer blocker passed in software

See re/EMMA_TIMER_BLOCKER.md for address-by-address evidence and commands.
A new research-only tools/pace_probe_emma_timer.py models channel0 of B000Dxxx,
local status/W1C ack, EMMA bit0x40 and CPU IP2. Genuine firmware ISR/HISR wakes
BOOTMain naturally: original semaphore obtain returns0 at9FC069F6, then event
initialization completes. Verified with two synthetic timer clock ratios. No
semaphore/PC/boot flag forcing. 8M steps yield173 real ISR acknowledgements and
substantially more instruction coverage. Directed model tests pass.

Next observed wait: APeriph8000A6D0 via9FC0630C. Its send fails channel gate
80013CCC=0; Ghidra finds initializer9FC03910 under normal path9FC03688. Current
BOOTMain takes another path because800081F8=1; trace its provenance next.
Hardware remains v046 EXP. New peripheral behavior is not yet in RTL/deployed.

## Continued Ghidra work: boot flag and embedded transport self-test

See re/BOOT_FLAG_AND_TRANSPORT_SELFTEST.md. Observed800081F8=1 is written at
BFC004FC from BFC0B444, which combines two hardware self-tests. A narrow
research FIFO data-port model now makes the first genuine self-test pass:
240 pattern writes/reads, return0. The second still times out and returns1;
no boot flags/PC/semaphores were forced.

Extracted six genuine TS packets and both expected DMA buffers from U202.
Independent PSI reassembly and CRC verification reconstruct both buffers
byte-for-byte:184 bytes and180 bytes. Deliberate CRC-bad sections are excluded.
Trailer meaning and PID routing remain ambiguous; documented precisely.
Next: infer indexed register/filter/DMA configuration so the genuine second
self-test can validate data produced by an actual configured demux model.
Hardware remains unchanged v046 EXP. This is new software evidence only.
