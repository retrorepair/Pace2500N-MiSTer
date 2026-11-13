# Vendored CPU: KI MiSTer R4600-compatible MIPS III

- Upstream: https://github.com/MiSTer-devel/Arcade-KillerInstinct_MiSTer
- Commit: 8d62121 (2026-11-11), files `rtl/cpu/*` and `rtl/ki_cpu_core.vhd`.
- Authors: Keith Conger (KI core); CPU derived from Robert Peip's N64 VR4300
  (https://github.com/MiSTer-devel/N64_MiSTer). Licence: GPL-3.0 (`LICENSE`).
- Purpose: base for the Pace 2500N's NEC VR4110 (see `re/CPU_PORT_PLAN.md`).

## Changes from upstream

None yet: this commit is the unmodified upstream files. Every later change is listed here with
its reason.
- `cpu_cop0.vhd`: Config bits 14:4 read the NEC VR4110's fixed fields (IC=4 16 KiB I-cache, DC=3
  8 KiB D-cache, 16-byte lines; `10110001100`) instead of the R4600's. Evidence: the Pace boot
  writes Config = 0x0002D8C2 at BFC00424 and reads it back at BFC00EF4.
- `cpu_cop0.vhd`, `cpu.vhd`: KSEG0 cacheability follows Config.K0 (K0 = 2 uncached, otherwise
  cached) for fetches and data; upstream KI always caches KSEG0. Evidence: the Pace boot routine at
  BFC008B4 pushes its return address with K0 = 2, sets K0 = 0, invalidates the whole D-cache by
  index, then pops it - correct only if the push went to memory uncached.
- `cpu_datacache.vhd`: replaced by an NEC VR4110 data cache (8 KiB, direct mapped, 16-byte lines,
  write back) - the N64 core's VR4300 data cache logic (same shape) on the KI cache's port. The KI
  cache (2-way 16 KiB, 32-byte lines, R4600) is kept as `cpu_datacache_ki.vhd` for reference, not
  built. Evidence for the shape: the firmware's cache init (BFC00910..) and flush (80007EAC..)
  sweep 8 KiB by index in 16-byte steps; Config DC=3. Write-backs leave in bus (address) order:
  the KI cache's big-endian half swap came from the N64's DDR3 RDRAM layout and is wrong for this
  bus (bus_to_cpu*/uncached path are address order).
- `cpu.vhd`: KI framebuffer windows (00030000-0007D800, partial-store and fill-order special
  cases) emptied - that range is ordinary RAM on the Pace.
- `cpu.vhd`: MIPS16 (EXTEND, JAL/JALX, no-delay-slot branches, PC-relative, ISA mode in address
  bit 0, MIPS16 delay-slot EPC), 32-bit JALX; checkpoint load port (GPR, HI/LO, CP0 via mtc0
  writes, start PC) for the Live core's STATE.bin; uncached reads carry a byte mask (device access
  size); no FPU (VR4110 has none; `cpu_FPU*.vhd` not built).
- `cpu_cop0.vhd`: Count rate generic (VR4110: 20.25 MHz), checkpoint write path, MIPS16 delay-slot
  EPC (the jump's own address).
