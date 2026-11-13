# Pace 2500N Sky Digibox for MiSTer — user guide

A MiSTer FPGA core that runs the **genuine Pace 2500N (Sky Digibox) firmware**:
the real Sky Guide boots, reads its listings from a transport stream and plays
MPEG-2 video with MP2 sound through the box's own decoder path. Channels are
served live from your PC (and optionally your Plex library), transcoded only
while the box is tuned to them, with period adverts and continuity between
programmes.

> This guide is kept current with every change. Developer and reverse-engineering
> notes are in `CURRENT_STATUS.md`, `handoff.md` and `re/`.

**Downloads:** [Releases](https://github.com/retrorepair/Pace2500N-MiSTer/releases)
(latest release **v0.6.3**) — `Pace2500N_V063.rbf` (the core),
`Pace2500N-MiSTer-files-v0.6.3.zip` (launcher + relay) and
`PaceChannelBuilder-v0.6.3-windows.zip` (the Windows app). The core contains no
firmware: it runs the flash dump you supply.

**v0.7.0** (not released yet; build it from source, see *Building the core*)
replaces the CPU with a pipelined, cached VR4110 - about 15 times faster - and
is the version this guide describes. v0.6.3 stays usable as a fallback.

## What works

| Area | State |
|------|-------|
| Firmware boot, Sky Guide, listings (TV Guide, A–Z, All Channels) | working |
| Running broadcast clock (from the MiSTer's RTC) | working |
| MPEG-2 video + MP2 audio, selected by the firmware when you pick a channel | working (v0.5.8+) |
| Streaming from the server share (file mode, any length) | working (v0.5.9; v0.6.1 adds tuner lock) |
| **Live channels from the PC playout server** — guide listings, channel numbers, now/next banner | **working (v0.6.1)** |
| Live channels — picture and sound of the channel you select, changing channel | **working (v0.6.2)** — the MPEG decoder's interrupts and header registers are now modelled |
| Core contains no firmware (boots from the flash dump it loads) — downloadable | **v0.6.3** |
| **New CPU**: pipelined NEC VR4110 with instruction and data caches, MIPS16, 75 MHz (~70 million instructions/s, the old CPU managed ~5) | **v0.7.0** |
| Keys respond straight away; TV Guide, Box Office and Services menus; back to the Guide from a channel | **working (v0.7.0)** |
| Interactive | shows the firmware's "no interactive services available" (none are broadcast) |
| Typing a channel number | "Channel Unavailable" - not yet |
| Channel sound continuing under the TV Guide | working |
| Plex library as a programme source (single titles or whole libraries) | working (Sky Movies from Plex, v0.7.0) |
| 7-day listings | generated; set `days` to 1 until proven on the firmware |
| EPG background music in the TV Guide | **working (13 Nov)**: with `"epg_music"` in the line-up, pressing TV Guide makes the box retune to its home transponder and play the period Guide music, as a real Digibox did; Sky returns to your channel. Needs the updated relay on the MiSTer (`tools/mister/install_relay.sh`). Background Music in Services > System Setup > Sound Settings |
| Teletext/VBI, A/V lip-sync | not yet |

## How it fits together

```
 Plex / files ──► PC: playout server ──► network ──► MiSTer HPS: relay ──► /tmp ring ──► core ──► firmware
 (sources)        (transcode on demand,               (pace_live_relay.py)  (image slot)   (demux,
                   guide data, adverts)                                                     MPEG decoder)
```

- **Channels are pure metadata** — a JSON line-up listing each channel's
  programmes, style and interstitial sets. No video files are made.
- **The box tunes, the PC plays.** When the firmware routes a channel's PIDs to
  its decoder, the core reports them; the relay asks the PC for that channel;
  the PC transcodes *what the schedule says is on now* and streams it. Change
  channel or leave the core and the transcode stops. Nothing is "on air" unless
  the box has tuned it. In the Guide (no channel tuned) only the listings are
  sent — no video is transcoded.
- **Period breaks.** ITV-style channels get centre and end breaks of real
  period adverts; Sky-style channels get Sky-length breaks; BBC-style channels
  get continuity (announcers, trailers, idents) and no adverts. Breaks are
  contiguous runs of spots exactly as they were recorded off air.

## 1. Install the core on the MiSTer

Copy to the MiSTer SD card:

| File | Where |
|------|-------|
| `Pace2500N_V070.rbf` (built from source; v0.6.3: `Pace2500N_V063.rbf` from Releases) | `/media/fat/_Other/` |
| `Pace2500N_V070_Live.mgl` (v0.6.3: `Pace2500N_V063_Live.mgl`, in the MiSTer files zip) | `/media/fat/` |
| Your firmware `FLASH_U202.bin` | `/media/fat/games/Pace2500N/` |
| Guide checkpoint `RAM.bin`, `STATE.bin` | `/media/fat/games/Pace2500N_GUIDE/` |

The firmware and checkpoint images are not distributed; they come from your own box.
The core boots entirely from the `FLASH_U202.bin` it loads - nothing from the
box is built into it.

## 2. The Windows app: Pace Channel Builder

A normal Windows program - nothing else to install (Python, ffmpeg and yt-dlp
are inside its folder).

- **Get it:** unzip `PaceChannelBuilder-v0.6.3-windows.zip` from
  [Releases](https://github.com/retrorepair/Pace2500N-MiSTer/releases) anywhere
  (e.g. `C:\PaceChannelBuilder`) and run `PaceChannelBuilder.exe`. Keep the
  whole folder together. Windows SmartScreen may warn the first time (the exe
  is not code-signed): *More info* -> *Run anyway*.
- **Run it:** *Pace Channel Builder* on the Desktop / Start menu, or
  `PaceChannelBuilder.exe` in that folder.
- **Upgrading:** close the app (it asks first while playout is running - the
  box loses its channels until you reopen it), replace the folder, start it
  again. Your settings, line-ups and adverts are kept (they are not in the
  app folder).
- **If something goes wrong:** the app writes `%APPDATA%\Pace2500N\app.log`
  (everything it did, errors, and a full dump if playout stops answering).
  The *Playout* tab shows whether the box is connected and when it last was.
- **Plex:** *Settings* tab -> **Sign in with Plex...**. Your browser opens Plex's
  own sign-in page; approve *Pace Channel Builder* and the app receives the
  token and finds your server by itself. You never copy a token by hand.
  (*Test connection* lists your libraries.)
- **Playout runs inside the app** and starts when the app opens (tick box in
  Settings). The *Playout* tab shows what each channel is showing and what is
  being streamed to the box. Keep the app open while you use the box.
- First time only: allow it through Windows Firewall if asked (the MiSTer
  connects to port 8250).
- Settings live in `%APPDATA%\Pace2500N\settings.json` (never in the project
  or on GitHub). The *Data folder* holds line-ups and `roms\` (ripped adverts).

To rebuild the app from source: `tools\build_app.bat` (needs Python and
PyInstaller on the build machine only; close the app first).

## 3. Install the relay on the MiSTer (once)

The two files are in the `relay` folder of the MiSTer files zip (or
`tools/mister/` in the source). From that folder on the PC (`MISTER` is the
MiSTer's address; the last address is your PC's LAN address, which the app's
Playout tab shows):

```bash
scp pace_live_relay.py install_relay.sh root@MISTER:/tmp/
```

```bash
ssh root@MISTER "sh /tmp/install_relay.sh 192.168.1.247:8250"
```

This puts the relay in `/media/fat/linux/pace/`, writes `relay.ini` (the PC
address — edit it if your PC's address changes) and adds one line to
`/media/fat/linux/user-startup.sh` so it starts at boot. It is idle until the
Pace core runs. Its log is `/tmp/pace_live_relay.log`. To upgrade, run the same
two commands with the new files; the old relay is stopped first.

## 4. Build channels

In the app:

- **Channels** - *Add* a channel; set its name, number, **style** (BBC style:
  continuity, no adverts / ITV style: terrestrial advert breaks / Sky style:
  satellite breaks), when its broadcast day starts, and tick the advert /
  continuity sets it uses. Add programmes with *Add files...* or
  *Add from Plex...* (pick a library, then a show and episodes - or **Add the
  whole library**: every film, or every episode of a TV library). The list
  repeats to fill the day. **Every change is saved as you make it** (the line-up
  file is shown at the top of the tab; a new one is `roms\lineup.json`), and a
  running playout picks it up a couple of seconds later - no Save or restart
  needed. A channel with no programmes yet stays off air.
- **Adverts & continuity** - search YouTube (e.g. `TVS adverts 1987`,
  `BBC1 continuity 1989`, `Sky One adverts 1994`), select results and *Rip
  selected* into a set named for the station and years. Videos you downloaded
  yourself go in with *Import videos into set...*.
  Long compilations (a whole evening's breaks in one video) are split
  automatically at the cuts between items - black frames with silence, black
  frames alone on hissy tapes, announcer pauses in long continuity. Select a set
  to see every spot with its time and length: *Play* (or double-click) previews
  it, *Exclude / include* drops anything that is not an advert, ident or
  continuity. Breaks use runs of spots exactly as they were broadcast, and never
  run across an excluded or over-long segment (e.g. a programme excerpt).
- **Schedule** - *Show today's guide* lists exactly what the box will show.
  *Find natural breaks* (once per programme, slow) moves ITV/Sky centre breaks
  to the programme's own fade-to-black points.

For scripting there are command-line equivalents (`tools/pace_channels.py`,
`tools/pace_playout.py`); a sample line-up is `tools/lineup.example.json`.

## 5. Watch

1. Open **Pace Channel Builder** on the PC (playout starts with it).
2. On the MiSTer load **Pace2500N_V070_Live** (or `Pace2500N_V063_Live`). The
   firmware starts in the Guide. After loading, the box gathers its listings:
   if ALL CHANNELS says *Searching for listings*, press Back Up (Esc) and open
   it again - with v0.7.0 the grid is there on the second visit, a couple of
   minutes after loading.
3. Press **TV Guide** (F1), choose **All Channels**, highlight a channel and
   press **Select** (Enter). After a few seconds (the PC starts the transcode at
   the scheduled point) the picture and sound appear.
   Keyboard/remote mapping: `KEYBOARD_REMOTE_MAP.md`.
4. To change channel, press TV Guide again and pick another one.

Channel numbering in the line-up maps to the box's services: channel *n*
(0-based) is SID 1001+n, video PID 0x200+0x10·n, audio PID 0x102+0x10·n.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Guide has no listings | Is the app open with playout *Running*? `/tmp/pace_live_relay.log` on the MiSTer shows `tuned:` lines and connection errors. |
| Relay can't reach the PC | `relay.ini` address (the app shows this PC's address on its Playout tab); Windows Firewall rule for the app on port 8250. |
| Picture freezes | Status page *Streaming* section; network speed (6.25 Mbit/s needed). |
| Wrong programme for the time | The MiSTer's clock (RTC) drives the guide; the PC uses its own clock — keep both on NTP. |

## Building the core

Quartus Prime Lite 17.0.2 (Cyclone V).

1. In the repository root: `quartus_sh --flow compile Pace2500N`. The root
   project (`Pace2500N.qsf`, `files.qip`) builds the current core (v0.7.0; the
   CPU is VHDL in `rtl/r4k/`, see `rtl/r4k/UPSTREAM.md`).
   No firmware is needed to build it: the Live core's boot-block memory is
   filled from your `FLASH_U202.bin` as the launcher loads it
   (`BOOT_LOAD(1)` in `rtl/Pace2500N_Transport.sv`, `rtl/pace_bootram.sv`).
2. Copy `output_files/Pace2500N.rbf` to the MiSTer as
   `/media/fat/_Other/Pace2500N_V070.rbf`.

Older development tops (`rtl/Pace2500N.sv`, `rtl/Pace2500N_Guide.sv`) still
cold-boot from an in-fabric boot ROM: make it from your own dump with
`python tools/make_bootrom.py` (writes `rom/bootloader_words.hex`). Those
builds contain firmware and must not be shared.

Development build trees live in `builds/` (not in git). Simulation benches are
in `sim/` (`iverilog -g2012`; e.g. `sim/tb_ts_live.sv`, `sim/tb_ts_stream.sv`).
The v0.7.0 CPU has its own: `sim/r4k/` (GHDL, the CPU alone against a reference
trace) and `sim/vl/` (Verilator: the CPU in the whole system with a transport
stream, checked instruction by instruction against the old CPU; `sim/vl/build.sh`).

The MPEG-2 decoder is from MiSTer_DVD (mpeg2fpga, GPL-3). The MiSTer
framework in `sys/` is GPL; see `LICENSE`.
