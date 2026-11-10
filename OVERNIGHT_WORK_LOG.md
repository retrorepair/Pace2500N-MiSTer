# Overnight work log

## 8 November daytime continuation, about13:10 onwards

Resolved serial52 completion via real RX path, captured original loader UART
output, validated both application images, and traced selected-image routine
12614 returning into permanent wait036F8 with ROM unchanged. User supplied
Colibri source URL; original downloads match both full flash files and the
separate protected loader exactly. Atmel-profile fresh61M-instruction run
also reaches the same wait; do not claim a full boot or a bad packaged dump.

Recovered the genuine dictionary-decompressed application code and imported
PaceAppRAM into Ghidra. All five initialized segments match original startup
execution byte-for-byte, including1029152 decompressed bytes. Standalone
entry-point harness is explicitly separate from protected-loader handoff.
It runs the application scheduler and has exposed frontend/I2C waits.

Driver-derived I2C channel0 completion now uses the genuine ISR and semaphore:
CA output3FFEA670 completes; NACK control sends no payload and returns error.
No I2C read data, signal lock, GUI, or successful loader handoff has been
fabricated. Hardware remains v046 EXP; all newer work is software RE.
See re/APPLICATION_HANDOFF_INVESTIGATION.md and CURRENT_STATUS.md.

Timebox explicitly requested by user: 2026-11-07 23:02:32 UTC to
2026-11-08 07:02:32 UTC (UK time). Keep progressing through the deadline.

## 23:02–23:11: checkpoint and independent CPU research

- Clean v0.4.4 full compilation completed, deployed and rechecked on MiSTer.
- Hardware strict endpoint/counters exactly match ModelSim; full DDR flash SHA
  matches U202; RAM pointers remain correct under video output.
- User CRT photo confirms analogue boot monitor; final SSH screenshot is full
  and readable with caption 0.4.4. A prior incomplete screenshot was misleading.
- Research interpreter now handles EXTEND and corrected field decoding.
  Directed encodings test distinct source/base registers, shift fields, NOT,
  compact return, and unsigned extended LI. Strict result remains unchanged.
- Experimental all-zero-MMIO run reaches 5,000,000 instructions, 545 EXTENDs,
  with no unsupported opcode before a poll at BFC0B118/B0009120, bit 0x20.
  This is software exploration, not verified peripheral semantics or full boot.

Next: freeze release/checkpoint; investigate polling register using Ghidra and
firmware traces, then advance an explicitly experimental RTL candidate.

## 23:11–23:51: independent ISA checks and first RTL candidate

- Sealed v044 full-source/RBF ZIP and unpacked checkpoint; archive hash is
  recorded in CURRENT_STATUS.md. Verified hardware remains available unchanged.
- Ghidra p-code emulator agrees with the research interpreter on 260 cases,
  including normal/extended MIPS16, register moves, memory, control transfers,
  MIPS32 REGIMM link/likely and HI/LO arithmetic. No skipped cases.
- Fixed an additional research-only BAL bug: link register was missing, sending
  a cached-ROM call stub to the wrong function. Implemented ERET selection of
  ErrorEPC/EPC and ISA low bit according to the NEC VR41xx manual.
- Explicitly guessed software profile (zero MMIO, B0009120=0x20) now executes
  ten million instructions with 254 timer interrupts, 255 Compare writes and
  actual firmware kernel tick 8000842C=0xFC. It reaches scheduler idle code.
  Count ticks are synthetic; neither peripheral semantics nor boot is proven.
- Added bounded 32-cycle multiply/divide RTL; 2,028 corner/random cases and
  reset pass. Integrated v045 decoder corrections, EXTEND paired reads,
  RAM instruction fetch, HI/LO arithmetic and ERET into the working CPU.
- All 260 independently captured Ghidra cases now also pass directly against
  the RTL, with DDR backpressure and delayed responses (Icarus).
- v045 is a source candidate, not yet built/deployed. Strict full-firmware
  regression and second-halfword boundary tests are next.

## 23:51–00:04: hardware candidates, timer and scheduler blocker

- v045 is compiling from frozen builds/v045 (ordinary strict/OSD policy).
  It includes the independently tested ISA decoder changes but no Count IRQ.
- v046 sources add free-running 50 MHz Count/Compare and architected IRQ/ERET
  handling, including EPC ISA and branch-delay BD for taken/untaken branches.
  Count frequency is approximate, not measured NEC timing. Experimental build
  builds/v046_exp is compiling with PACE_EXPERIMENTAL: policy=zero, B0009120=20.
  It has distinct on-screen/OSD EXP labels and actual IRQ/guess/policy telemetry.
- All ten ModelSim suites pass (boot, strict, memory, m16_pc, debug_uart,
  pal576i, oracle, fetch, timer, muldiv). Strict counters remain exact. The
  extra full original-firmware experimental 8M-instruction run is in progress.
- Long ordinary software run completed 50M instructions, 1831 interrupts,
  kernel tick=0x725; still scheduler idle. RAM dump retained in
  re/research_timed_09_ram.bin and report in research_timed_09.json.
- Firmware itself identifies Nucleus PLUS NEC4111 GHM 1.1.G1.3. Ghidra shows
  BOOTMain TCB at 80013AE0, entry9FC01291, created by BFC00E00. Last boot task
  path 9FC05638 -> 9FC06914 waits at 9FC069F0 on semaphore8000A820 forever;
  missing peripheral completion rather than frozen timer is the next blocker.
  This is an observation in the explicitly guessed software profile.
- Added exact-code guarded idle-loop acceleration in research tool only. A
  normal/accelerated 100k-instruction test agrees on every GPR, CP0, RAM byte,
  PC, delay state and interrupt event. Whole-firmware 50M comparison running.
- SSH UART baseline at 00:03:54 confirms MiSTer still runs verified v044.

## Resumption at07:20–07:27

Builds and full research simulation finished during session pause (see actual
log timestamps); no claim of continuous eight-hour unattended analysis.
Deployed v046 EXP as separate core, validated UART, fullDDR SHA, real kernel
tick and BOOTMain TCB via SSH, and captured a full monitor screenshot.
The missing upload flag was traced to a relative MGL path through a nonexistent
EXP game directory; absolute path fixed it without changing the RBF.
Current hardware reaches the same Nucleus scheduler/semaphore blocker as
software. v044 fallback is intact. See CURRENT_STATUS.md for hashes/details.

Final screenshot caveat: pre-upload EXP monitor is complete; repeated snapshots
after full-flash upload retain dynamic numbers but lose static labels. Cause
unresolved. CPU, flash, timer and scheduler verification use independent UART
and DDR checks. Do not present these captures as fully verified video output.

## Ghidra follow-up after user's next instruction

Resolved original EVTTick semaphore wait in software with a driver-derived
EMMA timer0/IP2 model. Genuine ISR acknowledges173/173 expirations by8M steps;
BOOTMain returns0 from its original obtain and initializes more tasks. Second
clock ratio reproduces success. Added driver listings/decompilation, unit test,
reports, RAM dumps and re/EMMA_TIMER_BLOCKER.md. No RTL/hardware changes here.
Next is APeriph wait / skipped channel initializer, with boot flag800081F8=1
selecting the relevant branch. Its provenance remains to investigate.

## Boot flag follow-up

Traced flag800081F8 to BFC004FC/BFC0B444 combining two early self-tests.
Added watch-only trace and data-port research model; first test now passes
240 writes/reads, second still fails honestly. Ghidra located embedded six-TS-
packet fixture and two expected DMA buffers. PSI/CRC parsing reconstructs both
expected buffers exactly; next step is guest-configured DMA/demux emulation.
Full evidence and uncertainty in re/BOOT_FLAG_AND_TRANSPORT_SELFTEST.md.
No FPGA changes this stage.

## Continued: demux self-test now passes end-to-end

Implemented guest-configured indexed ports, descriptor-driven flash DMA,
PSI/CRC/filtering and bounded RAM outputs. Both genuine early hardware tests
return0 in fresh run demux_fresh_04; boot flag is written0 by BFC004FC and
normal path9FC012E6 executes. Relocated DMA, PID/filter gates, CRC corruption,
bounds and genuine helper tests pass. Normal path now runs GPIO initializer
and NOR unlock/ID/reset (explicitly inferred table-supported profile).

Next is actual external peripheral response. Exploratory serial clock/IRQ
peer lets genuine firmware transmit decoded03011107 and03024100, then stops
without fabricating responses. Detailed evidence/assumptions and test commands
are in re/DEMUX_SELFTEST_PASSED.md. FPGA remains unchanged v046 EXP.
