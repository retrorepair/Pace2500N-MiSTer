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
| Live channels — picture and sound of the channel you select, changing channel | **working (v0.6.2)** — the MPEG decoder's interrupts and header registers are now modelled |
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
| `Pace2500N_V062.rbf` (from a build, see *Building*) | `/media/fat/_Other/` |
| `Pace2500N_V062_Live.mgl` | `/media/fat/` |
| Your firmware `FLASH_U202.bin` | `/media/fat/games/Pace2500N/` |
| Guide checkpoint `RAM.bin`, `STATE.bin` | `/media/fat/games/Pace2500N_GUIDE/` |

The firmware and checkpoint images are not distributed; they come from your own box.

## 2. The Windows app: Pace Channel Builder

A normal Windows program - nothing else to install (Python, ffmpeg and yt-dlp
are inside its folder).

- **Run it:** *Pace Channel Builder* on the Desktop / Start menu, or
  `dist\PaceChannelBuilder\PaceChannelBuilder.exe`. Keep the whole
  `PaceChannelBuilder` folder together if you move it.
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
PyInstaller on the build machine only).

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

In the app:

- **Channels** - *Add* a channel; set its name, number, **style** (BBC style:
  continuity, no adverts / ITV style: terrestrial advert breaks / Sky style:
  satellite breaks), when its broadcast day starts, and tick the advert /
  continuity sets it uses. Add programmes with *Add files...* or
  *Add from Plex...* (pick a library, a show, then episodes). The list repeats
  to fill the day. *Apply changes* saves.
- **Adverts & continuity** - search YouTube (e.g. `TVS adverts 1987`,
  `BBC1 continuity 1989`, `Sky One adverts 1994`), select results and *Rip
  selected* into a set named for the station and years. The app splits each
  recording into its original spots by itself.
- **Schedule** - *Show today's guide* lists exactly what the box will show.
  *Find natural breaks* (once per programme, slow) moves ITV/Sky centre breaks
  to the programme's own fade-to-black points.

For scripting there are command-line equivalents (`tools/pace_channels.py`,
`tools/pace_playout.py`); a sample line-up is `tools/lineup.example.json`.

## 5. Watch

1. Open **Pace Channel Builder** on the PC (playout starts with it).
2. On the MiSTer load **Pace2500N_V062_Live**. The firmware starts in the Guide.
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

Quartus Prime Lite 17.0.2 (Cyclone V). The working build trees are under
`builds/` (e.g. `builds/v062_irq`, made from `files.qip` of the previous build
plus current `rtl/` and `sys/`): `quartus_sh --flow compile Pace2500N`, output
`output_files/Pace2500N.rbf`. Simulation benches are in `sim/`
(`iverilog -g2012`; e.g. `sim/tb_ts_live.sv`, `sim/tb_ts_stream.sv`).

The MPEG-2 decoder is from MiSTer_DVD (mpeg2fpga, GPL-3). The MiSTer
framework in `sys/` is GPL; see `LICENSE`.
