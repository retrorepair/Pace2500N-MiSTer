# Pace 2500N real-firmware boot v0.4.4

Experimental MiSTer FPGA core for genuine Pace 2500N U202 firmware. The
picture is a live boot diagnostic, not a reconstructed Sky Guide. See
`CURRENT_STATUS.md` for measured build and hardware results, `handoff.md`
for the original architecture/history, and `re/NOTES.md` for corrected RE.

## Changes since v0.4.2

- Moved guest RAM to physical DDR `0x30000000` and full flash to `0x32000000`.
  The earlier mapping overlapped MiSTer's scaler and Linux framebuffer;
  hardware byte comparison exposed this after the first successful FPGA boot.
- Fixed the stale boot testbench and check all seven initial MMIO writes.
- Added a 50 MHz core PLL: MiSTer's video clock-select inputs require a PLL
  output. CPU, HPS I/O, DDR and video share that clock.
- Corrected MIPS16 LWPC/ADDIUPC bases in RTL and Python, including jump delay
  slots. The strict unknown read is **B0000012**, superseding B0000002.
- Added read-only HPS UART telemetry (115200, 8N1), one snapshot per second.
- Added strict boot, DDR lane/stall, PC-relative, UART and raster regressions.
- Bundled the imported MiSTer shell and platform QSF for offline preparation.
  File hashes are in `tools/mister_shell_sha256.json`; GPL text is `LICENSE`.

## Build

Open the included `Pace2500N.qpf` with Quartus 17.0.2 for Cyclone V. The
installed Lite edition has passed synthesis; check the status file for the
latest complete build. Run Analysis & Synthesis before full compilation.
The single synchronous 128 KiB boot ROM explicitly infers M10K memory.

`build_windows.bat` prepares project files only. It reuses the bundled shell
when present. `tools/build_project.ps1 -Compile` requests a full build if
Quartus is on PATH. The Python alternative is `python tools/build_project.py`;
`--ki <checkout>` selects another local platform reference. Do not assume a
new upstream shell is equivalent to the recorded source.

Full compilation produces `output_files/Pace2500N.rbf`. Copy it into
MiSTer's `_Other` directory. The boot block is embedded: the first strict boot
needs no firmware upload. Full application flash can be selected with F12:
`Load FLASH_U202.bin`, followed by `Restart actual firmware`. The genuine
2 MiB image is in `firmware/FLASH_U202.bin`.

Preserve the working MiSTer RGB settings. Intended analogue raster is
625 lines/frame, 50 interlaced fields/s, nominal 15.625 kHz horizontal and
640x576 active samples. Sync equalising/serration is simplified; verify CRT
lock physically. Default unknown-read policy is Halt. Other policies return
experimental guesses and do not establish correct NEC hardware behaviour.

## Validation

From this project directory:

```powershell
python tools/verify_firmware.py
python tools/test_probe_pc.py
./tools/run_sim.ps1
```

`run_sim.ps1 -Test` accepts `boot`, `strict`, `memory`, `m16_pc`, `debug_uart`
or `pal576i`. Its default ModelSim path is the installed Quartus 17 directory;
use `-ModelSim <path>` for another installation. The original firmware remains
byte-for-byte intact. Synthetic CPU unit tests replace ROM words in simulation
only. The strict test uses the original ROM and a 16 MiB RAM model with stalls.

Expected corrected strict endpoint: PC BFC01E1C, HALT 03, MIPS16, unknown read
B0000012, 3,178,988 retired instructions, 1,770,706 RAM writes, 12 MMIO writes.
The Python probe starts after the two leading NOPs and counts 3,178,986.

The CPU is incomplete and NEC EMMA graphics/audio/TS hardware is unimplemented.
Full flash upload and real DDR behaviour require physical validation; the
loaded flag currently detects the final upload address rather than proving
that every preceding beat was committed. Further CPU work is in
`re/CPU_TODO.md`. No successful Sky Guide execution is claimed.
