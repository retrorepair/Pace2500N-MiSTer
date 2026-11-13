# CPU port plan: pipelined, cached VR4110 from the KI MiSTer CPU

Decision (user, 11 Nov 2026): replace `rtl/pace_firmware_cpu.sv` (multi-cycle, 8.5 clocks per
instruction at 50 MHz, 5.9 MIPS, no D-cache) with a pipelined, cached CPU derived from the Killer
Instinct MiSTer core's CPU, so the firmware runs near the real box's speed (NEC: 66-100 MIPS).
The old CPU stays the shipping core until the new one passes on hardware.

## Source

- github.com/MiSTer-devel/Arcade-KillerInstinct_MiSTer, commit 8d62121 (2026-11-11), `rtl/cpu/`
  and `rtl/ki_cpu_core.vhd`. GPL-3.0 (Keith Conger; CPU derived from Robert Peip's N64 VR4300,
  github.com/MiSTer-devel/N64_MiSTer, also GPL-3.0). R4600-compatible MIPS III, 5-stage pipeline
  (stage 1 fetch, 2 decode, 3 execute, 4 memory, 5 writeback), core on clk2x (100 MHz in KI),
  memory interface on clk1x (50 MHz), cpu_cdc_fifo between them.
- Vendored into `rtl/r4k/` with `UPSTREAM.md`; every change from upstream is listed there.

## Sizing (measured, standalone, 5CSEBA6U23I7)

KI CPU with the FPU removed and the SDRAM direct-fill path tied off: 6,943 ALMs, 40 M10K, 18 DSP
(7,473 ALMs with KI's performance settings). Our CPU: 5,883 ALMs, 145 M10K (128 = boot block).
Whole design after the swap: ~80% ALMs, ~440/553 M10K. Timing: -3.06 ns at 100 MHz with KI's
settings (~77 MHz): writeback/forward -> stall1 and branch -> I-cache fill. Default settings:
worst path was the 2-way D-cache MRU, which a direct-mapped D-cache does not have.

## What the firmware needs (evidence)

1. **Big-endian** MIPS (U202, RAM). Generic `LITTLE_ENDIAN => false` (the N64 default).
2. **MIPS16** (original VR4100-series MIPS16, not microMIPS): the Guide's o-code interpreter and
   much of the OS run in it. Not in the KI/N64 CPU. Semantics already implemented and proven on
   hardware in `rtl/pace_firmware_cpu.sv` (`S_EXEC` mips16 branch, `S_M16_EXTEND`, `S_M16_JUMP`):
   EXTEND prefix; JAL/JALX (32-bit, delay slot, ISA switch); JR/JALR with delay slots and ISA mode
   from bit 0; MIPS16 branches B/BEQZ/BNEZ/BTEQZ/BTNEZ have **no** delay slot; PC-relative
   ADDIU/LW use the instruction's (or, in a delay slot, the jump's) aligned PC; SLT/SLTI/CMP/CMPI
   write T (r24); EPC bit 0 = ISA mode, exception in a delay slot reports the jump.
3. **Caches with the VR4110 shape** (boot code bfc008dc..: I-cache index-store-tag + fill over
   0x80000000..0x80004000 step 16; D-cache index-store-tag over 0x2000 step 16; runtime flush
   80007eac: D Index Writeback Invalidate over 0x2000 step 16; 80007ed4: D Hit Writeback):
   I-cache 16 KiB, D-cache 8 KiB, **direct-mapped, 16-byte lines**, write-back. KI's D-cache is
   2-way 16 KiB with 32-byte lines (R4600): an 8 KiB index flush would leave half of it dirty. The
   N64 upstream D-cache (VR4300) is exactly 8 KiB direct-mapped 16-byte lines; KI's grew from it.
4. **Config.K0** decides KSEG0 cacheability; the firmware rewrites it (80007ef0..80007f18: clear
   bits 2:0, or set bit 1).
5. **No FPU** on the VR4110: COP1 = Coprocessor Unusable.
6. **No TLB use** observed: the current CPU has no TLB and runs everything (it halts on any
   mapped access or TLB instruction, and never does). Keep the TLB unless it costs timing/area.
7. **Exceptions/interrupts**: vector 0x80000180 (BEV=0) / 0xBFC00380; the Guide's handler
   jumps to 0x800D4788. Interrupt lines: IP2 = EMMA interrupt controller (`io_irq`), IP7 = timer
   (Count/Compare). Count at 20.25 MHz wall time (`WALL_COUNT`): the firmware reloads Compare with
   202500 and the EMMA timer with 810000 for the same 10 ms tick.
8. **Memory map** (as the current CPU): RAM 16 MiB at physical 0 (DDR 0x30000000); flash 2 MiB at
   physical 0x1FC00000 (DDR 0x32000000; boot block included - a cached CPU reads it from flash as
   the real one does, so `pace_bootram` goes); MMIO B0000000-B00FFFFF, B2000000-B20FFFFF,
   B4080000-B408FFFF, B4180000 (byte write) through the existing `io_*` port and
   `pace_mmio_response`; 1F800000-1FBFFFFF reads from flash (EXTERNAL_MMIO mapping).
9. **Checkpoint start**: the Live core resumes the Guide from RAM.bin + STATE.bin (GPRs, CP0,
   PC, mips16, timer_armed, hi, lo, retired via `checkpoint_*`). The new CPU needs the same
   loading port (the N64 CPU had savestate ports; KI dropped them).

## Phases

1. Vendor unmodified; GHDL build (`/opt/ghdl-altera` has altera_mf); bench with a DDR/MMIO
   memory model and the KI retire export (`cpu_export`) as an architectural trace.
2. Big-endian, FPU out, VR4110 cache geometry, Config.K0, VR4110 PRId/Config. Verify on the
   32-bit boot path: trace vs `pace_firmware_cpu` (same instruction stream and register writes)
   up to the first MIPS16 instruction.
3. MIPS16 in decode (halfword fetch, EXTEND, JAL/JALX, no-delay-slot branches, PC-relative).
   Verify: full trace equality vs the old CPU from the Guide checkpoint, interrupts injected at
   the same retired-instruction index.
4. Integration: clk at the real CPU rate if it closes timing (target 81 MHz class; measure),
   memory bridge to the DDR3 arbiter and MMIO, checkpoint port, telemetry. Remove boot-block M10K.
5. Hardware: Guide boots from checkpoint, listings on the first ALL CHANNELS visit, tunes, profile.

## Progress log

- 11 Nov: vendored (`rtl/r4k`, KI 8d62121). GHDL bench `sim/r4k/tb_r4k.vhd` + reference trace
  `sim/r4k/tb_ref_trace.sv` + `sim/r4k/compare_trace.py`. Changes so far: VR4110 Config fields;
  KSEG0 cacheability from Config.K0. Real U202 boot from reset: **300,000 instructions identical**
  to `pace_firmware_cpu` (pc and register results). First MIPS16 instruction at 3,178,986; first
  interrupt at 3,557,226 (reference timing).
- D-cache decision: KI's D-cache (2-way, 32-byte lines, way prediction, read-ahead, framebuffer
  partial stores, SDRAM fast path) cannot be reshaped by parameters. Remapping KI's index cache
  ops would make the boot's 8 KiB sweeps complete, but `D HitInv` on a 16-byte DMA buffer line
  would also drop the other half of KI's 32-byte line (possibly dirty), unlike the VR4110 - not
  faithful. Plan: a new VR4110 D-cache (8 KiB, direct-mapped, 16-byte lines, write-back) on KI's
  D-cache port, its logic from the N64 CPU's D-cache (the VR4300's, the same shape); read-ahead,
  framebuffer and fast-path ports tied off.
- 11 Nov night: VR4110 D-cache, MIPS16 translator, checkpoint port done. From reset 300,000
  instructions identical; from the MIPS16 checkpoint 378,240 identical up to the first timer
  interrupt (taken 2 instructions later: different Count rate in simulation).
- 12 Nov: first v0.7.0 hardware run (fits: 77 % ALMs, 78 % RAM blocks, 92 % DSP; 75 MHz
  CPU clock +0.36 ns). The Guide resumed but sat in its idle loop (800D35D8, waiting on flags
  that interrupt handlers set) at 1.4 M instructions/s, with no interrupts. Cause: the CP0
  write-port mux (`wIndex`/`wValue`, checkpoint vs mtc0) and `kseg0_uncached` had been placed
  inside cpu_cop0's simulation-only export block (`synthesis translate_off`), so on hardware
  no CP0 register was ever written (Quartus warning 10541: "never assigned"). Moved out.
  Simulation with the hardware bridge's latency and grant-to-data gap (`tb_r4k` generics
  LAT/GAP) runs the same Guide checkpoint correctly.
- Build note: three `quartus_map` parallel-synthesis helpers orphaned by a stopped build cannot
  be killed and hold files in the project's `db/`; synthesis there hangs with no CPU use.
  Builds run in a clean copy (`../Pace2500N_build070`, sources only) until a reboot clears them.
- With CP0 fixed: 75 M instructions/s (1 per clk2x cycle), then the firmware's TLB-refill panic
  (`j 80000F1C`) after ~7.5 M. Hardware retire trace + bus trace (below) showed it: a store,
  then two loads that HIT (`lw s1,36(s0)` at 8011E468, `lw a2,0x74(pc)` at 800D1028) got each
  other's data, and the jalr through a2 went to 801737C8 (a task list head). Cause: the new
  D-cache lacked KI's REREAD/ram_stale ("LOADS WITHOUT THE BUBBLE", cpu_datacache_ki.vhd): in
  IDLE the data RAMs read the NEXT access's doubleword, so a load after a store (or a busy
  state) that the pipeline does not stall for was answered from the wrong read. Fixed as KI
  does (REREAD state, ram_stale flag) with KI's two simulation assertions. The bench now has
  `LAT_RAND` (random per-access latency) - fixed latency never produced the pattern.
- With the D-cache fixed the Guide ran but ignored keys (its serial poll stopped after one byte);
  a 1024-entry snapshot showed a second panic: `lw v1,0xa0(pc)` at 800A92F4 - the target of a
  taken MIPS16 `bnez` - used 800A9344 as its base. The annulled wrong-path slot after the
  branch was `jr ra`, and the translator's "PC-relative in a jump's delay slot uses the jump's
  address" test did not exclude an annulled jump. Fixed (`executeIgnoreNext = '0'`).
- 12 Nov night: system simulation (sim/vl): rtl/r4k converted to Verilog with `ghdl --synth`
  (GHDL 6; 4.1/6.0 crash on the dead 64-bit region decode, removed in the converted copy only),
  Verilator, with pace_r4k.sv, the device models, blitter, demux and a DDR model with random
  latency/busy; tb_shadow.sv replays it into the old CPU (pace_firmware_cpu) and stops at the
  first difference. With a TV Guide key press it diverged after 35,078,909 instructions: an
  interrupt in the delay slot of the MIPS16 `jalr` at 800CD8EF (the call to TCT_Unprotect,
  800D3ACC) saved EPC = the slot, BD = 0, so eret skipped the call and the protection stayed
  owned - the deadlock. Cause: KI's chainedDelaySlot test assumes 4-byte instructions (delay
  slot at +4); a MIPS16 JR/JALR's is at +2. Fixed (cpu.vhd chainedDelaySlot).
- 13 Nov: with that fixed the Guide ran and keys worked - but only without a transport stream;
  with the Live stream a key press gave the video's C1 (OSD descriptor rejected). The system
  simulation got a TS feed (+ts=FILE) and diverged after 24,078 instructions: an interrupt
  taken on the annulled wrong-path halfword after a taken MIPS16 compact branch (8001DA85 ->
  8001DAAD) saved EPC = that halfword (8001DA87), so eret resumed on the fall-through. Fixed:
  no interrupt is attached to a slot EXEIgnoreNext annuls; it is taken at the next one.
- Bring-up diagnostics (temporary, `Pace2500N_Transport.sv`, `pace_r4k.sv`): telemetry IR = live
  EPC, RAM = live BadVAddr, GUESS = stage-4 memory stall cycles, IRQ = exception entries, RD =
  live Cause/Status. PROF frames carry a frozen retire trace (last 128 instructions: pc,
  register, value) and bus trace (last 64 CPU transactions), frozen when 80000048 (the refill
  handler's panic branch) retires; read with `tools`-style script `trace070.py` on the MiSTer.

## After the CPU (user's order, 11 Nov 2026)

Seen on hardware with v0.6.3; to do once the new CPU is in, in this order:

1. **Stuck in the channel carousel:** once in it, the box will not go back to the main menu.
2. **BOX OFFICE, SERVICES and INTERACTIVE** buttons do nothing.
3. **Typing a channel number** always gives "Channel Unavailable".
4. **EPG background music** (firmware audio path only; see memory notes).
5. **Programme synopsis:** the **i** button (F6 / I) shows "Programme synopsis is not
   available" (expected: the line-up sends no synopsis data yet). Fill it from the Plex
   metadata of the file the channel is playing, where there is one.
6. **Audio normalisation** (added 12 Nov 2026): even out loudness between channels and
   programmes, so switching channel or moving into an advert doesn't jump in volume.
