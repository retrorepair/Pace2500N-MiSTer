# Pace 2500N / Sky Digital MiSTer FPGA — Project Handoff

**Continuation:** Read `CURRENT_STATUS.md` first for later fixes, measured
Quartus results and HDL regressions. The latest session is directly below; the original
7 Nov snapshot further down is retained for history only (it predates everything that works).

## Session 13 Nov 2026 - v0.7.0 pipelined CPU usable; EPG music and channel numbers open

**State:** v0.7.0 (`_Other/Pace2500N_V070.rbf`, `Pace2500N_V070_Live.mgl`) runs the firmware
on a KI-derived pipelined, cached VR4110 (`rtl/r4k/`, bridge `rtl/pace_r4k.sv`; plan and
progress log in `re/CPU_PORT_PLAN.md`). On hardware: keys respond at once; TV Guide, Box
Office, Services menus; ALL CHANNELS listings (second visit); channel play from the Guide
(BBC1, and Sky Movies films from Plex); back to the Guide from a channel. Fit: 82% ALMs,
80% RAM, 92% DSP; HDMI scaler path slack about -0.1 ns (not the CPU).

**Bugs found and fixed in the CPU port** (all ours, not KI's): CP0 write mux inside
`translate_off`; D-cache missing REREAD/ram_stale; PC-relative base taken from an annulled
jump; chained-delay-slot test assuming +4 (MIPS16 is +2); IRQ taken on an annulled slot.

**System sim** (`sim/vl/`): GHDL 6 converts the VHDL CPU to Verilog (`synth.sh`), Verilator
builds `tb_sys.sv` (CPU + devices + blitter + demux + DDR model + TS feed + key sequences)
and `tb_shadow.sv` (old CPU lockstep). Useful plusargs: `+keys=80,01 +keyat +keygap`,
`+ts= +tsgap=64`, `+mlog=` (every device access), `+watchval=`, `+watchaddr=` (cached
loads/stores of a word, with the 400 instructions before), `+natives` (every o-code native
call with its o-code PC in a3). Build: `OBJ=/tmp/vl_objN bash sim/vl/build.sh nosynth` in WSL.

**App / playout:** Channel Builder auto-saves (new line-up -> `roms/lineup.json`), adds whole
Plex libraries, reloads playout; Sky Movies = 182 Plex films + the 1998 continuities. SI
version comes from the channel set (fixed the box tuning BBC1 for a new channel). Line-up key
`epg_music` (experiment, on in `roms/lineup_mock.json`) adds the "EPG Background Audio"
service (SID 4152, audio 0x288, own 0xB1 record, 0x91 linkage at it) and serves the MP2.

**Open, in priority order (user):**
1. **EPG background music - WORKING (13 Nov, hardware), the authentic way.** Pressing TV Guide
   on a channel makes the FIRMWARE retune to the home transponder (11778) and route the EPG
   Background Audio service (audio 0x288); Sky retunes back to the channel. How it was found:
   the Guide o-code loads setting key "SSBM" (Sound Settings Background Music) into global
   0x80477228 (Guide globals base 0x8045CB64 + 0x1A6C4; `aa` pushes the base, `09` adds a
   4-byte offset); where SSBM is on, the o-code (9FC930FD / 9FC9338B -> function 9FC4E03D)
   calls native (12,0x24) = 800CB74C -> 800CB69C(0x90): the BAT/SDT linkage of TYPE 0x90 names
   the background-audio service ((12,0x23) is 0x91 = home service, (12,0x25) is 0x94). Playout
   (line-up key `epg_music`) now builds Sky's layout: home transponder 11778 V (TSID 0) with the
   music service and the full guide; TV channels on 12207 V (TSID 1) with now/next only; 0x91 ->
   first TV channel, 0x90 -> the music service. The relay reads the tuned frequency from guest
   RAM (MPEG manager 0x80163198+0x1C, BCD) and sends `freq=` so playout serves the transport the
   box is on. Not yet heard by ear on this run (UART telemetry flooded); same service/PIDs
   decoded audio-only with MP2 sync earlier the same day. LSST (0x80477224) is subtitles, not music.
2. **Typed channel numbers -> "Channel Unavailable".** Reproduced on hardware from TV mode:
   EVERY number (101, 106) gives "NNN Channel Unavailable" with no tune attempt, while banner
   Up/Down + SELECT tunes fine. The box's received BAT 0xB1 entries are intact in RAM (sid,
   type 1, channel id 3000+, number 101/103/106/104, number<<4|6). The sim cannot reach TV mode
   from the Guide checkpoint (Sky key never tunes in sim, even pressed at 6-7.5 s), so this
   needs hardware RAM inspection (`scratchpad/ramdump.py` style, DDR 0x30000000) or a sim fix.
3. **Synopsis (Plex).** Done app-side: Plex summaries are fetched once per programme (cached
   in library_cache.json, also stored when a library is added) and sent as standard OpenTV
   summary tables (0xA8-0xAB, PIDs 0x40-0x47, descriptor 0xB9), and guide text is folded to
   what the firmware's Huffman table can code. The box does NOT show them yet ("Programme
   synopsis is not available"). Firmware facts: the EPG section parser 800C95D0 takes 0xA0-0xA3
   (titles, 0xB5), 0xA4-0xA7 ("kind 2": records of descriptor 0xBC = 9-byte cross references
   channel id/start/event id, callback 800C6B68) and 0xB0; 0xB9 text is decoded by 800CA028,
   reached from the 0xBC path (800C9F58) and from a request-driven single-event parser 800C3990
   (section: ext=channel id, [8-9] mjd, [10-11] ?, [12-13] ?, [14-15] 12-bit length,
   descriptors from 16). The live request table (0x80165048) shows no new request when Info is
   pressed. Next: find what creates "type 3" requests / what Info reads.
4. EPG music in the Guide (above); first-visit "Searching for listings"; audio normalisation
   (backlog item 6 in `re/CPU_PORT_PLAN.md`); HDMI scaler timing slack.
5. Note: with `epg_music` on, the music service is the box's home service and shows as radio
   channel "0 EPG Background Audio" in the banner Up/Down cycle; Sky with no channel tunes it.

**User-supplied references (13 Nov) - read before working on the Guide music or Guide look:**
- https://www.tvforum.co.uk/tvhome/sky-guide-music-27594 - the EPG listings are received on
  the same transponder as the EPG music. User's reading: the Guide is in effect its own
  channel (in the Guide all channels are left and the box is tuned only to the listings/EPG),
  so if the listings are fed authentically on that transponder the music should play
  organically. Feed it the authentic way, not as a special case.
- https://www.reddit.com/r/olddigibox/comments/cfd4xl/proud_owner_of_two_digiboxes_that_still_has_the/
- https://en.everybodywiki.com/Sky_EPG_(Electronic_Program_Guide) - photos show a Sky logo in
  the top-left of the Guide; our Guide leaves that area empty. Find what fills it and why we
  do not draw it.
- From the tvforum thread (2008 posters, not official): the box loads its channel list from a
  "default transponder" at boot and prefers EPG data from it; that is the transponder with the
  EPG background audio. A box that cannot see the default transponder boots with no channel
  numbers and no EPG (a box given another default got listings but no music and only half the
  channels). Pressing TV Guide TUNES AWAY from the current channel to the EPG transponder (the
  channel's sound stops) and leaving the Guide retunes back. Ordinary transponders carry only a
  couple of hours of now/next (Search and Scan banner); the full 7 days and synopses need the
  EPG transponder. Sky+ lost EPG music/info when both tuners were recording.
- Reddit and everybodywiki refuse automated fetches (403); read them in a browser if needed.
- Sky logo, top-left of the Guide - OPEN. Known: the reference project measured that the Guide's
  OSD blits start at x=128 and never paint the top-left 128x112 ("may be where the video window
  belongs, or a blit nothing has issued yet"). The firmware has an "image" device beside "video"
  (flash strings at 0x26640/0x26648) - a candidate MPEG-still path. Measured 13 Nov: entering the
  Guide (now a real retune to 11778) writes no video PID for a still in the first seconds
  (video 0x0230 disabled, audio 1FFF, then the music). Next: trace who would draw that corner -
  the "image" device's users, and any PES/section filter the Guide sets on the home transponder.
- Also (user, via Gemini - unverified): the box tunes its "default transponder" for the full
  guide; "EPG Background Audio" is an unencrypted audio-only service on that transponder.
- Measured 13 Nov: the o-code word 0x80477228 is the Background Music setting (1=ON; toggling
  it in Sound Settings flips it, no A/V access). 0x80477224 beside it is 1 in the checkpoint,
  0 live; after a core load it goes 0 -> 1 about 11 s in (polled from the HPS).

**Rules (unchanged):** faithful decompilation only; no firmware, RAM images, TS files or
`rom/bootloader_words.hex` in git or releases; Plex token only in
`%APPDATA%\Pace2500N\settings.json`; README is the user guide.

---

# Original snapshot (7 Nov 2026) - historical

**Snapshot:** 7 November 2026  
**Current candidate:** `Pace2500N_RealFirmwareBoot_v042_Lean.zip` (v0.4.2)  
**Current result:** source and genuine firmware assets exist; **no successful v0.4.2 Quartus synthesis, fitter pass, `.rbf`, or DE10-Nano/CRT boot has been verified**.

## 1. Non-negotiable project goal

Create a **real Pace Sky Digital Digibox emulation** for the MiSTer FPGA DE10-Nano, running the original receiver's firmware and eventually showing the **firmware-generated** Sky Guide on an analogue RGB CRT TV. Simulate the associated NEC EMMA hardware, memory, DVB transport/EPG, inputs, smartcard interface where needed, and ultimately real video/audio playback. An assistant-drawn Sky-like interface is **not** the objective. The immediate milestone is much smaller: produce a manageable, synthesizable MiSTer `.rbf` that executes original bootloader instructions and displays **meaningful, live boot progress** over a 15 kHz RGB CRT connection.

The user can compile Quartus locally, but expects **real, working source** rather than repeated architectural discussions. Keep changes small, diagnose measured results, and provide corrected files. Do not claim a graphical Sky Guide or successful FPGA boot until observed.

## 2. Hardware, firmware and reference architecture

- **Target receiver:** Pace 2500N, Sky model family **9F04**, circa 2000; dumped application is from approximately **September 2002**, not the original 1998 launch firmware.
- **Likely SoC family:** NEC EMMA / µPD6103x, possibly **µPD61032** (NDS VideoGuard variant); **exact Pace board chip marking not independently confirmed**. NEC references include the September 1999 µPD6103x product documentation. A detailed NEC hardware register map has not been found.
- **CPU:** Big-endian MIPS, using both standard 32-bit instructions and **MIPS16** (not microMIPS). ISA changes, branch-delay slots, exceptions and cache effects matter. Exact VR4110-compatible details require confirmation.
- **Firmware:** original JTAG dumps `FLASH_U202.bin` and `FLASH_U203.bin`, **2,097,152 bytes each**, in `firmware/` of v0.4.2. U202 SHA-256: `32f6b2e84d0c4c4ec280a72f2d080e4b6fa5e68e8438ef712f34f97f63d38c7f`; U203 SHA-256: `7832d619b63e369bdd4a0f3de8dd73c98a99285d96c94a8bb0a39fe829ce1f40`.
- **Flash banks:** differ by 30 bytes, confined to `0x1A0000`–`0x1A001F`. Original dumper said this represented dual OTA-update banks. The 128 KiB bootloader at `0x000000`–`0x01FFFF` matches both; original dumper zeroed four Digibox serial bytes at `0x1FFF8`.
- **Boot:** first actual reset instructions at U202 offset `0x000008`: `3C08BFC0 25080408 01000008 00000000` (`lui/addiu/jr/nop`), jumping to `0xBFC00408`. Application jump code at offset `0x2002C` points to `0xBFC2048C`.
- **MiSTer hardware:** DE10-Nano, analogue RGB to a CRT TV. Use **625-line, 50-field/s interlaced timing, 15.625 kHz horizontal** (usually described as **576i/50** in active-picture terms), **not 480i/60** or 240p. The generated sync is still an approximation and must be verified on the real CRT. Exact native chip video modes and assets have *not* been extracted/verified.
- **Upstream public FPGA reference:** `https://github.com/MiSTer-devel/Arcade-KillerInstinct_MiSTer`. This has a substantial synthesizable **MIPS III** VHDL CPU, but the current Pace project **does not instantiate it**. Only its MiSTer `sys/` board shell/pin configuration is reused. Its CPU is not a drop-in solution because Pace needs MIPS16 and NEC-specific differences. Respect upstream GPL licensing.

**Original source documentation:** `flashdump_PACE2500N.zip` with `info.txt`, `PACE2500N_Bootloader.zip`, `DigiboxTool.zip`. The earlier `Pace2200sm_*.pdf` and `Pace2200sch_*.pdf` are for the **different Pace 2200 ST20 system**; do not assume those schematics apply to the 2500N.

## 3. Confirmed reverse-engineering evidence (software probe only)

The supplied `probe_strict.json` records execution in an **experimental Python CPU interpreter**, not execution on FPGA:

- **3,178,986 interpreted instructions** until an unknown 16-bit MMIO read, `0xB0000002`, at `PC 0xBFC01E1C` in MIPS16 mode.
- **MIPS32 → MIPS16** transition: instruction at `0xBFC00578` (`JALX`) enters `0xBFC01E18`.
- Initial seven real-firmware MMIO writes, in order:

  | Guest address | Written value |
  |---|---|
  | `0xB0000430` | `0x40000021` |
  | `0xB0000440` | `0x00000141` |
  | `0xB0000410` | `0x00000001` |
  | `0xB0000400` | `0x00000023` |
  | `0xB0000600` | `0x00000200` |
  | `0xB0000610` | `0x00232323` |
  | `0xB2006000` | `0x00000080` |

- After a long RAM initialisation loop, additional writes were recorded to `0xB0000040`, `0xB0000030`, `0xB0000060`, `0xB0000050`.
- The `probe_experimental.json` run returns guessed values to unspecified hardware reads, reaches **3,203,621 interpreted instructions** and then stops on unsupported MIPS16 `0xF140` at `0xBFC0AF06`. **This is not proof of correct hardware behaviour or firmware boot.**
- Static/interpretive register associations remain hypotheses until NEC documentation or repeatable functional evidence supports them.

## 4. History and exact present blocker

1. Earlier v0.1–v0.2 projects were standalone FPGA diagnostics, not normal MiSTer menu cores. v0.3 added a fake Guide-like graphics prototype and a firmware viewer; that visual prototype was **rejected** because the real firmware must generate the UI.
2. v0.4 provided a standard MiSTer `emu`/`sys_top` shell, an incomplete custom MIPS32/MIPS16 executor, ROM, DDR3 bridge and 576i CRT boot monitor.
3. **v0.4 initial Quartus failure:** `Error (10028): Can't resolve multiple constant drivers ... Pace2500N.sv(83)`. The error was caused by connecting the `hps_io` **output** `.sd_buff_wr` to `1'b0`. **v0.4.1 fixed this** to `.sd_buff_wr()` (unconnected). This is the one confirmed compiler issue addressed in that release.
4. User's **v0.4.1** Analysis & Synthesis ran for **around 90 minutes without reaching the fitter**. This is the current observed performance problem. It was **suspected**, not proven, that multiple independently addressed reads of a 32,768-word × 32-bit firmware ROM triggered inefficient synthesis/multiplexer expansion.
5. **v0.4.2 Lean** was produced to address that suspicion: ROM changed to a single synchronous inferred M10K port and video hex browser removed. **v0.4.2 synthesis and final FPGA resources/performance are not yet tested.** The user requested this handoff **before attempting the new build**.

Do not describe the v0.4.2 fix as verified until an A&S report shows inferred memory and realistic runtime/resource counts.

## 5. Current v0.4.2 project files and implementation

Archive root after extraction: `Pace2500N/`.

```text
Pace2500N/
├── README.md
├── CHANGELOG_v042.txt
├── QUARTUS_FIX_v041.txt
├── build_windows.bat
├── Pace2500N.sdc
├── files.qip
├── firmware/
│   ├── FLASH_U202.bin       # genuine full 2 MiB bank, supplied
│   └── FLASH_U203.bin       # second genuine 2 MiB bank, supplied
├── rom/
│   ├── bootloader_words.hex # genuine first 128 KiB of U202, BE 32-bit words
│   ├── font8x8.hex
│   └── monitor.hex          # DIAGNOSTIC MONITOR text, not Sky firmware UI
├── rtl/
│   ├── Pace2500N.sv        # MiSTer emu top, HPS file upload and DDR interface
│   ├── pace_bootrom.sv      # single-port synchronous M10K ROM
│   ├── pace_firmware_cpu.sv # experimental MIPS32/MIPS16 executor
│   ├── pace_pal576i.sv      # 625/50 RGB interlace timing (simplified sync)
│   └── pace_boot_monitor.sv # live status screen (PC, instruction, MMIO, etc.)
├── sim/
│   └── tb_boot.sv           # WARNING: stale; see section 7
└── tools/
    ├── build_project.ps1   # downloads/copies KI sys/, creates .qpf/.qsf
    ├── build_project.py    # alternative Python generator
    ├── make_monitor.py
    ├── pace_probe.py       # software interpreter
    └── verify_firmware.py  # reproducibility/integrity checks
```

**HDL-specific facts:**

- `rtl/Pace2500N.sv` uses the standard MiSTer `emu` ports from `sys/emu_ports.vh`, `hps_io`, and the `sys/` support files sourced from Killer Instinct. The KI **CPU itself is not used**.
- `rtl/pace_bootrom.sv` declares `(* ramstyle = "M10K" *) reg [31:0] words [0:32767]`, initialises it from `rom/bootloader_words.hex`, and has **one registered read port**.
- The CPU accesses the protected flash region via ROM, and the remainder of U202 via a MiSTer DDR3 upload if the full `.bin` has been selected. It also uses DDR3 for emulated RAM. **The correctness of byte lanes, address translations, DDR3 request/ready sequencing and memory map is unverified on MiSTer.**
- Top-level video drives `CLK_VIDEO = CLK_50M` and a 12.5 MHz pixel enable from `pace_pal576i.sv`. Nominal raster is 800 samples per 64 µs line, 625 lines/25 frames and 50 fields/s; 640×576 active sample layout with alternating fields. PAL equalising/serration pulses are **not** complete or broadcast-exact.
- The RGB picture is **only a diagnostic monitor**. There is **no** actual NEC EMMA overlay/OSD decoder, MPEG-2 video/audio output, TS demux, tuner, smartcard, Sky Guide graphics renderer, or firmware-controlled output plane. Even a successful core build will *not* show Sky Guide yet.
- The CPU lacks comprehensive CP0, exceptions, TLB, cache, interrupts and complete MIPS16. The `CACHE` opcode is explicitly treated as a no-op; MMIO reads may halt or return guesses. These shortcuts can change real firmware execution.

## 6. Build and MiSTer deployment — intended procedure, NOT yet proven

1. Extract `Pace2500N_RealFirmwareBoot_v042_Lean.zip` in a fresh Windows folder.
2. Run `build_windows.bat`. It calls `tools/build_project.ps1`, downloads the public Killer Instinct repository if needed, copies `sys/`, and generates `Pace2500N.qpf` / `.qsf`. Requires an Internet connection for the automatic download, or use `tools/build_project.py --ki <existing KI checkout>`.
3. Open `Pace2500N.qpf` in **Quartus Prime Standard** for Cyclone V. **Run Analysis & Synthesis only first**. Record duration, RAM Summary/M10K use, ALM/register count, memory-inference warnings and the last progress messages. Stop/report if it behaves like v0.4.1.
4. Only after A&S succeeds, run full compilation, producing `output_files/Pace2500N.rbf` (assuming project QSF settings and tool versions allow it).
5. Copy `Pace2500N.rbf` to `/media/fat/_Other/` (visible as **Other** in the MiSTer menu). Optionally place `FLASH_U202.bin` at `/media/fat/games/Pace2500N/FLASH_U202.bin` for convenient browsing; this is a convenient storage path, **not a mandatory auto-load convention**.
6. Load **Other → Pace2500N**, then press **F12**. The **actual v0.4.2** `CONF_STR` is:

   ```text
   F0,BIN,Load FLASH_U202.bin;
   O[2:1],Unknown hardware read,Halt,Return zero,Return FFFF,Return one;
   R0,Restart actual firmware;
   ```

   Choose the 2 MiB `FLASH_U202.bin`, then Restart actual firmware. Default **Halt** is the most interpretable first test; guessed MMIO responses should be used only for exploration, not treated as proof.
7. With a correctly configured analogue MiSTer-to-RGB/SCART connection, a **live 576i boot monitor** is the expected *intended* screen. If black/unstable, first distinguish video timing / physical connection failure from CPU/DDR failure. MiSTer's existing working `MiSTer.ini` analogue settings should be preserved where possible.
8. Photograph the CRT monitor and record **PC, instruction, retired instruction count, HALT code, last MMIO read/write and full-flash-loaded flag**. Provide Quartus reports for synthesis problems.

## 7. Newly identified issues that must not be overlooked

**Found while preparing this handoff; not yet patched:**

- **The included `sim/tb_boot.sv` is stale after v0.4.2.** It instantiates removed CPU ports `.rom_view_index` and `.rom_view_data` (the hex viewer was removed) and its example `iverilog` command omits `rtl/pace_bootrom.sv`. This testbench **cannot be relied upon for v0.4.2 validation without correction**. Fix it first if using simulation as a guard against regressions. The testbench also has a `wait(...)` timeout and checks the first seven writes; preserve that purpose.
- **Performance claim not yet established.** The one-port synchronous ROM should improve RAM inference, but whether Quartus maps the source as intended must be checked in **RAM Summary and mapping messages**. A 90-minute A&S stall in v0.4.1 does not by itself prove ROM muxes were the cause; investigate other combinational paths if v0.4.2 still stalls.
- **Quartus build is not equivalent to boot.** CPU/MMIO/DDR correctness, MIPS16 mode handling and PAL CRT timing still need on-hardware verification.
- **Target SoC and address functions are not fully documented.** Do not invent semantics for `0xB0000002` or other registers; label policies and guessed responses as experimental.
- **Firmware-derived assets are not yet driving RGB.** The monitor font/text comes from `rom/font8x8.hex` and `rom/monitor.hex`, which are project diagnostics, not recovered Sky graphics. Native receiver OSD/video work is a later milestone.
- **Upstream KI shell is fetched from a moving `main` branch.** If files change, the project generator may behave differently; for reproducible builds, eventually pin an upstream commit and archive/record its SHA.

## 8. What to do next, in priority order

1. **Do not attempt another blind 90-minute compile.** First fix the stale `sim/tb_boot.sv` to match `pace_firmware_cpu` + `pace_bootrom`, and run minimal HDL compilation/simulation if possible. Catch parameter/port and ROM timing errors before Quartus fitting.
2. Check v0.4.2 **Analysis & Synthesis only**, particularly inferred ROM M10K use. If synthesis is slow, use the last log phase, resource estimation and isolated module builds to identify the actual heavy logic before rewriting large blocks.
3. If it synthesizes, fit/generate the `.rbf` and test **real PAL 15 kHz RGB on the user's CRT**. Capture a photo and live debug values. Distinguish stable scanout from CPU boot progress.
4. Validate **MiSTer HPS U202 upload and DDR3 access**, including every 16-bit upload beat, read-after-write and endianness; ensure full flash completion flag is genuine. Build a small deterministic memory test if necessary.
5. Use the Python probe and captured register trace as a reference, then extend verified MIPS16 instructions, branch/return semantics, CP0, exceptions and hardware-access models. Prefer observable deterministic tests over repeated blind MMIO guessing.
6. Only after CPU and memory are trustworthy: reconstruct NEC EMMA graphics, PAL video encoder / overlay planes, firmware OSD assets and DVB/EPG input sufficient for original Guide UI.

**Success criteria for next handoff:** A&S log and RAM/ALM counts + successfully created `.rbf` + photo of stable CRT boot monitor + observed PC/HALT trace from the actual FPGA. **Not** a cosmetically convincing but fabricated Sky menu.

## 9. Important reference/archive filenames

- **Current candidate:** `Pace2500N_RealFirmwareBoot_v042_Lean.zip` — project source and both full flash dumps.
- **Previous build:** `Pace2500N_RealFirmwareBoot_v041_QuartusFix.zip` — had fixed multi-driver output; user's A&S took about 90 minutes without reaching fitter.
- **Original firmware dumps:** `flashdump_PACE2500N.zip`.
- **Original protected bootloader:** `PACE2500N_Bootloader.zip`.
- **Historic JTAG dump program/manual:** `DigiboxTool.zip`.
- **Software trace history:** `pace2500n_stage4_cpu_probe.zip`, and `probe_strict.json` / `probe_experimental.json` inside the v0.4.2 project.
- **Upstream shell / alternative CPU:** https://github.com/MiSTer-devel/Arcade-KillerInstinct_MiSTer
- **NEC product overview found in earlier research:** https://tvsat.com.pl/PDF/U/UPD61032_nec.pdf — product-family description, **not** a confirmed Pace 2500N register-programming manual.

---

**Resume instruction:** Treat this handoff and the newest project source as the working baseline. The user's immediate priority is a **reasonably fast and reproducible Quartus build that shows real firmware-execution progress on a PAL CRT**. Start by fixing the v0.4.2 stale testbench and validating synthesis; don't spend another turn creating a mock Guide or restating plans.
