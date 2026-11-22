# Pace 2500N Sky Digibox for MiSTer — user guide

A MiSTer FPGA core that runs the **genuine Pace 2500N (Sky Digibox) firmware**:
the real Sky Guide boots, reads its listings from a transport stream and plays
MPEG-2 video with MP2 sound through the box's own decoder path. Channels are
served live from your PC (and optionally your Plex library), transcoded only
while the box is tuned to them, with period adverts and continuity between
programmes.

**Latest release: V080B + Channel Builder 0.8.0B**, on the
[`cold-boot` branch](https://github.com/retrorepair/Pace2500N-MiSTer/tree/cold-boot),
tested on 22 November 2026. The firmware cold-boots entirely in FPGA from the
original flash image, with an EEPROM save and live transport stream.
**No `RAM.bin` or `STATE.bin` checkpoint is loaded.**

This build adds live Teletext pages, page 888 text subtitles and automatic
cropping of 4:3 programmes stored inside a 16:9 picture. All 48 non-HDMI timing
checks and two four-minute hardware tests passed. Guide backgrounds and the
corner logo survive a trip to live TV and back. Boot remains slow; physical-TV
checks of the new live clock and timed subtitle overlay are still pending.

**Downloads:** [V080B / v0.8.0-beta.2](https://github.com/retrorepair/Pace2500N-MiSTer/releases/tag/v0.8.0-beta.2)
contains the tested `Pace2500N_V080B.rbf`, matching Live launcher and relay,
Channel Builder 0.8.0B Windows app, and `SHA256SUMS.txt`. **V080B is the latest
full release**, with GitHub's prerelease flag cleared. The existing tag and
asset names are retained to preserve download links. Older v0.7.x packages use their own matching launcher/app and
[checkpoint-era instructions](https://github.com/retrorepair/Pace2500N-MiSTer/blob/v0.7.7-rc3/README.md).
The installation instructions below describe V080B from this branch.

For continuation and detailed validation, see [current status](https://github.com/retrorepair/Pace2500N-MiSTer/blob/cold-boot/CURRENT_STATUS.md),
[handoff](https://github.com/retrorepair/Pace2500N-MiSTer/blob/cold-boot/handoff.md), [live Teletext](https://github.com/retrorepair/Pace2500N-MiSTer/blob/cold-boot/LIVE_TELETEXT.md) and the
[expansion plan](https://github.com/retrorepair/Pace2500N-MiSTer/blob/cold-boot/EXPANSION_PLAN.md).

The current implementation is on **cold-boot**; the main branch retains the
earlier source. The instructions below install the V080B release.

## 1. Copy the files to your MiSTer SD card

From the [V080B release](https://github.com/retrorepair/Pace2500N-MiSTer/releases/latest),
download the RBF, **MiSTer files zip** and **Windows app zip**. Unzip both zip files.

Copy these files onto your MiSTer SD card. Create the folders if needed:

| File | Folder on the SD card |
|---|---|
| `Pace2500N_V080B.rbf` | `_Other` |
| `Pace2500N_V080B_Live.mgl` (from the MiSTer files zip) | `_Other` |
| Your original `FLASH_U202.bin` (2 MiB) | `games/Pace2500N` |
| `install_relay.sh` and `pace_live_relay.py` (from the MiSTer files zip) | `Scripts` |

You supply the firmware; it is not included. **You do not need `RAM.bin` or
`STATE.bin`.** The installer creates the EEPROM save for you and keeps any
existing save. These folder names start at the SD card's root (shown as
`/media/fat/` when browsing the MiSTer over the network).

## 2. Set up Channel Builder on your PC

1. Put the extracted **PaceChannelBuilder** folder somewhere permanent, such
   as `C:\Pace2500N`. Keep everything inside it together.
2. Run **PaceChannelBuilder.exe**. In **Settings**, choose your original
   `FLASH_U202.bin` under **Firmware image**. Set **Days of listings** to **7**.
3. If you want to use Plex, click **Sign in with Plex...** in Settings and
   approve it in your browser. **Test connection** checks your libraries.
4. Allow the app through Windows Firewall if asked. Open the **Playout** tab
   and note the PC address shown there, including `:8250`.

Keep the PC and app running while you watch. Your video and audio files stay
on the PC; you do not copy them to the MiSTer.

## 3. Run the installer on MiSTer

1. On the MiSTer, open **Scripts**. Allow scripts if MiSTer asks.
2. Select **install_relay** (the `install_relay.sh` file you copied).
3. Using a keyboard, enter the **PC address from Channel Builder's Playout
   tab**, for example `192.168.1.10:8250`, then press Enter. Use your PC's
   address here, not the MiSTer's address.
4. When it finishes, press Enter to return to the menu.

**No SSH or PC terminal is needed.** You normally do this only once. The
connection starts automatically each time MiSTer starts. To change the PC
address or update the relay, copy the latest two files into `Scripts` and run
it again. Press Enter at the address prompt to keep the existing address.

## 4. Add channels and Guide music

Channel Builder saves changes automatically. A **line-up** is your saved set
of channels and their programmes; its file is shown at the top of **Channels**.
You can keep several using **New line-up**, **Open...** and **Save as...**.

### Make a channel from your videos or Plex

1. On **Channels**, click **Add**. Give it a name and an unused channel number.
2. Choose its **Guide genre** and **Style**. BBC style has continuity without
   adverts; ITV and Sky styles add advert breaks when advert sets are selected.
   Leave the broadcast start time alone unless you want a particular schedule.
3. Click **Add files...** for videos on the PC, or **Add from Plex...** for
   Plex films/episodes. The Plex picker can also **Add the whole library**.
4. Use **Up / Down** beneath the programme list to set the running order.
   The programmes repeat to fill the schedule. A channel with no programmes
   stays off air.

The **Schedule** tab's **Show today's guide** lets you check the result.

### Add internet TV

On **Channels**, click **Add IPTV**, choose the stations you want and click
**Add selected**. You can also use **Paste a stream URL instead** for a direct
stream address. Keep **Official sources only** selected in the picker.

Programme listings and descriptions are fetched automatically where a matching
TV guide exists. The picker's **Listings** column shows which stations have
one; others show **Live TV**. Each station is given its own channel number.

### Add internet radio

Open **Music & Radio** and click **Add starter stations** for a ready-made
selection. To add your own, click **New**, enter a station name, an unused
number from **800–899** and a direct audio-stream URL, then **Save station**.
A station's current track appears in the Guide when its stream supplies that
information. On MiSTer, choose **TV Guide → Music & Radio** or type its number.

### Add the Guide background music

1. On **Channels**, click **Choose audio…** beside **EPG background audio**.
2. Pick your music file on the PC: **MP2, MP3, WAV, FLAC, M4A or OGG**. For
   example, select your `sky_epg_music_2002.mp2` if you have it. Keep the file
   in that location; it is streamed from the PC and is not bundled with the app.
3. On the box, set **Services → System Setup → Sound Settings → Background
   Music** to **On**.

The music choice is saved with the current line-up. It loops while you browse
the EPG, including Guide, All Channels, Box Office and Services. Returning to
live TV restores channel audio. **Clear** removes the music choice; without a
working music file the EPG is silent.

### Optional: add adverts and continuity

In **Adverts & continuity**, search for videos, select results and click
**Rip selected**, or use **Import videos into set...** for your own files.
Give the set a useful name, such as a station and year. Long recordings are
split into spots; preview them and use **Exclude / include** to skip unwanted
parts. Then select the set under that channel's **Adverts / continuity sets**.
**Find natural breaks** in Schedule can place breaks at programme fades.

## 5. Watch

1. In Channel Builder, open **Playout** and click **Start playout** if it is
   not already **Running**. Keep the app open.
2. On MiSTer, open **Other** and select **Pace2500N_V080B_Live**. Leave
   **Boot: Cold from flash** selected in the core OSD. Initial boot and Guide
   loading take time; wait for the firmware to finish starting.
3. Press **TV Guide** (F1), choose **All Channels**, highlight a channel and
   press **Select** (Enter). After a few seconds (the PC starts the transcode at
   the scheduled point) the picture and sound appear.
   Keyboard/IR remote mapping: [KEYBOARD_REMOTE_MAP.md](https://github.com/retrorepair/Pace2500N-MiSTer/blob/cold-boot/KEYBOARD_REMOTE_MAP.md).
4. To change channel, press TV Guide again and pick another one.

### Keep your setup when upgrading

Close the app, replace its program folder with the new download, then reopen
it. Settings normally stay in `%APPDATA%\Pace2500N`; line-ups and media stay
in the **Data folder** selected in Settings. Keep those files when upgrading.
Optional portable mode uses `data/settings.json` beside the app when an empty
`portable.flag` file is present. The app log is `%APPDATA%\Pace2500N\app.log`.

For live Teletext and subtitles, use the switches in **Settings**. Subtitle
delay is adjustable from -10 to +10 seconds, initially +0.7. These choices do
not change Plex's general audio/subtitle preferences.

## 6. Teletext, subtitles and picture fit

Use a Teletext-capable TV with the analogue RGB/SCART output and composite sync
(`composite_sync=1`). In the core OSD, **Live Teletext: On** is the default.
Use the **TV's own Text and page-number controls**:

| Page | Contents |
|---|---|
| 100 | Index |
| 101 | Receiver test with a changing clock |
| 200 onward | Current channel now/next listings, four channels per page |
| 300 | BBC News headlines |
| 400 | Weather from the approximate public-IP location |
| 500 | Recent official MiSTer Main commits |
| 888 | English subtitles, where a usable track exists |

F11 starts/cancels the original **fixed** page 100 test for 30 seconds; live
pages resume afterwards. F8/T is the Pace firmware's Text command. See
[LIVE_TELETEXT.md](https://github.com/retrorepair/Pace2500N-MiSTer/blob/cold-boot/LIVE_TELETEXT.md) for the distinction and full setup.

Plex supports usable text tracks such as SRT. IPTV needs separate text captions
(for example WebVTT) or a Teletext subtitle stream. There is **no OCR** for
image-only PGS/VobSub/DVB bitmap subtitles, and no text extraction from burned-in
captions. English text is selected rather than substituting foreign-language
tracks. The tested Red Dwarf rip has English PGS and Czech SRT, so it needs an
English text track for page 888. TV subtitle overlay timing still needs feedback.

News, weather and MiSTer pages refresh in the background; a failed feed retains
its last successful page with a fetch time or shows an unavailable message.
Weather estimates location from the PC connection's **public egress IP**, not
the router's private address. A VPN or ISP location can affect that estimate.

**Fill 4:3 programmes stored inside a 16:9 picture** analyses scheduled files
and Plex sources in the background. Three separated samples must agree before
the side bars are cropped. Results are cached; an uncached title may need a
retune or the next programme start after analysis. Genuine wide material keeps
the OSD letterbox behaviour. Live IPTV is not automatically cropped by this
feature. A real Red Dwarf source was detected as 1440×1080 inside 1920×1080.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Guide has no listings | Is the app open with playout *Running*? `/tmp/pace_live_relay.log` on the MiSTer shows `tuned:` lines and connection errors. |
| Relay can't reach the PC | `relay.ini` address (the app shows this PC's address on its Playout tab); Windows Firewall rule for the app on port 8250. |
| Picture freezes | Status page *Streaming* section; network speed (6.25 Mbit/s needed). |
| Wrong programme for the time | The MiSTer's clock (RTC) drives the guide; the PC uses its own clock — keep both on NTP. |
| Teletext stays on the old fixed test | Wait for the F11 test window to finish, then select page 101 to check live updates. |
| Page 888 is empty | Check for a usable English text/Teletext track and that subtitles are enabled in the app. Image-only tracks are not converted. |
| Caption timing is off | Adjust **Subtitle delay** in app Settings; report the source and observed offset. |
| 4:3 programme still has side bars | Allow background analysis to complete, then retune. Detection is conservative and applies to scheduled files/Plex. |

## Source and developer notes

For screenshots, build instructions and detailed validation, see the
[full development guide](https://github.com/retrorepair/Pace2500N-MiSTer/blob/cold-boot/README.md).
Use the `cold-boot` branch when building V080B from source.
