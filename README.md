# Pace 2500N Sky Digibox for MiSTer — user guide

A MiSTer FPGA core that runs the **genuine Pace 2500N (Sky Digibox) firmware**:
the real Sky Guide boots, reads its listings from a transport stream and plays
MPEG-2 video with MP2 sound through the box's own decoder path. Channels are
served live from your PC (and optionally your Plex library), transcoded only
while the box is tuned to them, with period adverts and continuity between
programmes.

> This guide is kept current with every change. Developer and reverse-engineering
> notes are in `CURRENT_STATUS.md`, `handoff.md` and `re/`.

## What works

| Area | State |
|------|-------|
| Firmware boot, Sky Guide, listings (TV Guide, A–Z, All Channels) | working |
| Running broadcast clock (from the MiSTer's RTC) | working |
| MPEG-2 video + MP2 audio, selected by the firmware when you pick a channel | working (v0.5.8+) |
| Streaming from the server share (file mode, any length) | working (v0.5.9; v0.6.1 adds tuner lock) |
| **Live channels from the PC playout server** — guide listings, channel numbers, now/next banner | **working (v0.6.1)** |
| Live channels — picture and sound of the channel you select | **first channel after boot works**; selecting a second channel shows its banner but the firmware does not start its decoder yet (being investigated: MPEG decoder status registers not modelled) |
| Channel sound continuing under the TV Guide | working |
| Plex library as a programme source | written; untested until a Plex token is entered |
| 7-day listings | generated; set `days` to 1 until proven on the firmware |
| EPG background music, teletext/VBI, A/V lip-sync | not yet |

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
| `Pace2500N_V061.rbf` (from a build, see *Building*) | `/media/fat/_Other/` |
| `Pace2500N_V061_Live.mgl` | `/media/fat/` |
| Your firmware `FLASH_U202.bin` | `/media/fat/games/Pace2500N/` |
| Guide checkpoint `RAM.bin`, `STATE.bin` | `/media/fat/games/Pace2500N_GUIDE/` |

The firmware and checkpoint images are not distributed; they come from your own box.

## 2. Set up the PC (Windows)

1. Install Python 3.12 (`py -3` must work).
2. Get ffmpeg for Windows: unzip the gyan.dev *release essentials* build into
   `Pace2500N/third_party/` (the tools find `third_party/ffmpeg-*/bin/ffmpeg.exe`).
3. For ripping adverts: `py -3 -m pip install --user yt-dlp`.
4. Start the **Channel Builder**: `py -3 tools\pace_builder.pyw`.
   - *Settings*: check the ffmpeg path; for Plex enter the server address
     (e.g. `http://192.168.1.53:32400`) and your **Plex token**, then *Test Plex*.
     Settings live in `%APPDATA%\Pace2500N\settings.json`, never in the project.
5. Allow Python through Windows Firewall when asked (the MiSTer connects to port 8250).

## 3. Install the relay on the MiSTer (once)

From the PC (replace the address with your PC's LAN address):

```bash
scp tools/mister/pace_live_relay.py tools/mister/install_relay.sh root@MISTER:/tmp/
```

```bash
ssh root@MISTER "sh /tmp/install_relay.sh 192.168.1.247:8250"
```

This puts the relay in `/media/fat/linux/pace/`, writes `relay.ini` (the PC
address — edit it if your PC's address changes) and adds one line to
`/media/fat/linux/user-startup.sh` so it starts at boot. It is idle until the
Pace core runs. Its log is `/tmp/pace_live_relay.log`.

## 4. Build channels

In the Channel Builder:

- **Channels tab** — *Add* a channel, set name, number, style (`bbc`, `itv`,
  `sky`), the time the broadcast day starts (UTC) and its interstitial sets
  (`roms/interstitials/<set>`, several separated by `;`). Add programmes from
  files or *Add from Plex*. The programme list repeats to fill the day.
- **Interstitials tab** — search YouTube (e.g. `TVS adverts 1987`,
  `BBC1 continuity 1989`, `Sky One adverts 1994`), select results and *Rip
  selected* into a set named for the station and years. Each set is analysed
  for the cuts between spots automatically. Ripped files stay under `roms/`
  and are never committed.
- **Schedule tab** — *Prepare* finds natural break points (black frames) in
  ITV/Sky programmes once (cached); *Build today's guide* shows exactly what the
  box's guide will list.
- **Playout tab** — *Start playout server*. *Open status page* shows every
  channel's now/next and what is being streamed to the box.

Command-line equivalents: `py -3 tools/pace_channels.py schedule LINEUP.json`,
`... prepare LINEUP.json`, `... analyse roms/interstitials/<set>`,
`py -3 tools/pace_playout.py LINEUP.json`. A sample line-up is
`tools/lineup.example.json`; `tools/make_mock_lineup.py` writes the mock
BBC1/ITV/Sky One line-up used for testing.

## 5. Watch

1. Start the playout server on the PC.
2. On the MiSTer load **Pace2500N_V061_Live**. The firmware starts in the Guide.
3. Open the guide / *All Channels* and select a channel; after a few seconds
   (the PC starts the transcode at the scheduled point) the picture appears.
   Keyboard/remote mapping: `KEYBOARD_REMOTE_MAP.md`.

Channel numbering in the line-up maps to the box's services: channel *n*
(0-based) is SID 1001+n, video PID 0x200+0x10·n, audio PID 0x102+0x10·n.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Guide has no listings | Is the playout server running? `/tmp/pace_live_relay.log` on the MiSTer shows `tuned:` lines and connection errors. |
| Relay can't reach the PC | `relay.ini` address; Windows Firewall rule for Python on port 8250. |
| Picture freezes | Status page *Streaming* section; network speed (6.25 Mbit/s needed). |
| Wrong programme for the time | The MiSTer's clock (RTC) drives the guide; the PC uses its own clock — keep both on NTP. |

## Building the core

Quartus Prime Lite 17.0.2 (Cyclone V). The working build trees are under
`builds/` (e.g. `builds/v061_live`, made from `files.qip` of the previous build
plus current `rtl/` and `sys/`): `quartus_sh --flow compile Pace2500N`, output
`output_files/Pace2500N.rbf`. Simulation benches are in `sim/`
(`iverilog -g2012`; e.g. `sim/tb_ts_live.sv`, `sim/tb_ts_stream.sv`).

The MPEG-2 decoder is from MiSTer_DVD (mpeg2fpga, GPL-3). The MiSTer
framework in `sys/` is GPL; see `LICENSE`.
