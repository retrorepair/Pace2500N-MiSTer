# Pace 2500N / Sky Digital MiSTer FPGA — Project Handoff

**Continuation:** Read `CURRENT_STATUS.md` first for later fixes, measured
Quartus results and HDL regressions. The latest session is directly below; the original
7 Nov snapshot further down is retained for history only (it predates everything that works).

## Session 17 Nov 2026 (night) - IPTV channels

- A line-up channel with `"iptv": URL` (no programmes) is a `LiveChannel` (pace_channels.py):
  same service/PID layout as a scheduled channel, "Live TV" in each six-hour block, genre from
  the line-up. Playout `Session.live()` opens the stream with ffmpeg (HLS gets
  `-extension_picky 0` - Amagi/FAST streams splice adverts as oddly named segments), converts
  it like a channel (576i MPEG-2, levelled MP2, letterbox) and reopens it if it drops.
  Channel Builder: **Add IPTV** (URL + name; next free number; genre/number editable).
- Tested on hardware: 601 Retro Toons (Pluto TV Retro Toons GB, from iptv-org's UK list via
  jmp2.uk) - typed 601 tunes it, picture + sound, banner "Live TV", 781 kB/s, 0 underruns/30 s.
  Line-up backup before the change: `roms/lineup_mock.before-iptv.json`.
- Sources: iptv-org (11,558 entries; UK 308) and Free-TV. Only official streams are used: the
  iptv-org "Boomerang" entries (FR/IT/TH/US) are re-streams of the paid channel from bare IPs and
  scraper scripts, as are several "BBC One" entries; not used. UK Boomerang became Cartoonito
  (2023). Next: XMLTV guide data (iptv-org/epg, tvg-id) for real titles; an M3U picker in the
  app.

## Session 17 Nov 2026 (late) - reminders route, stale listings, screenshots

- REMINDERS: the user set one successfully FROM THE CHANNEL (banner Search Time -> future
  programme -> Select). Every refusal seen by the agent was from the ALL CHANNELS grid
  (incl. from a grid synopsis). So the grid route is what fails - compare the two paths.
- STALE LISTINGS FIXED (`7fe4b55`): TV title/synopsis sections now carry a content-derived
  version (they were always 0, so a box kept stale blocks after any schedule change -> "..no
  listings available"). Not in rc2.
- Screenshots in `docs/screenshots/`, gallery in README (`9ec1c85`).

## Session 17 Nov 2026 (evening) - genres, advert spots, Guide music timing

- GENRES (`4b29652`): the Guide's genre pages list channels by the 3-bit genre in SDT 0xB2.
  Verified: 6 Movies, 3 Entertainment, 4 Music & Radio (1 Specialist, 2 Kids, 5 News & Docs,
  7 Sports from Sky decoders, unverified). Line-up `genre` per channel ("auto" = Plex films ->
  Movies, else commonest Plex genre of the programmes via the show's tags, else
  Entertainment); Channel Builder has a Guide genre picker. Programme-level genre (the title
  record's genre byte) is still 0.
- GAMESMASTER "random show": a centre break used a 145.7 s "spot" from an off-air ad-break rip
  (programme footage the black+silence cut finder could not split). ITV/Sky-style breaks now
  refuse segments over 90 s (BBC continuity keeps 240 s).
- GUIDE MUSIC TIMING (musictime.py polls guest RAM + the ring status): the firmware retunes to
  11778 within ~0.7 s of the TV Guide key and routes audio 0x288 either ~0.1 s later or ~14-15 s
  later (5 runs: 0.9, 1.0, 0.9 s and 14.1, 14.7, 15.7 s). Routing happens before any data from
  the new playout session arrives, so the wait is the firmware's own decision; PC + relay add
  ~0.3 s. Empty present/following sections for the music service (as for every service) were
  added; they did not clearly change it. Next: find what the Guide waits on in the slow case.

## Session 17 Nov 2026 (late afternoon) - 7-day listings, grid synopses

- 7 DAYS: the user's settings had `days: 1` (left from the early "keep it at 1" advice), so
  playout only ever sent today and +24 Hours said "Further schedule information is not
  available". Set to 7 (backup `%APPDATA%\Pace2500N\settings.json.bak-days1`): Today..Monday
  all present on V077. The box fetches a day when it is first shown; at one repeat per 9 s loop a
  day took ~40 s to fill ("searching for listings"). The carousel now repeats later days and
  synopses every 2 s when the 133-packet tick has room (every 4 s, else once a loop): ~94/133
  packets per tick for this line-up, loop still exactly 9.0 s.
- GRID SYNOPSES: BBC2 worked, Sky Movies showed "Programme synopsis is not available". The
  type-2 request was correct and completed (listing 0x0BBD, event 8, MJD 0xEFB1, block 2,
  state 1002 -> 1004). Cause: Plex film summaries decode to 300-400 characters, the firmware
  decodes 0xB9 into a 0x101-byte buffer (800CA028 -> 800BECF0 dstmax 0x101), and one long text
  (E.T., 412) spoiled its whole block. Synopses are now cut to 255 characters at a word: grid
  Info on Ghostbusters shows its synopsis. Channel4 GamesMaster has no Plex summary at all.
- REMINDERS: still refused on V074 with current playout AND on V077 with v0.7.4 playout
  (`31ee306`, run from a worktree) - so not the playout or core changes since v0.7.4 (user
  thought they worked between 0.7.2 and 0.7.4). Personal Planner is empty. Lead: bookings live in
  an EEPROM file (`/eeprom/book`, flash string at 0x9FCC2F54); if our 24C128 model cannot write
  or the checkpoint EEPROM lacks the file, every reminder fails - trace the I2C/EEPROM traffic
  when Select is pressed on a future programme.
- The MOVIES (and other genre) pages are empty: our title records carry genre 0. Separate item.

## Session 17 Nov 2026 (afternoon) - channel numbers fixed; reminders open

- Line-up renumbered (backup `roms/lineup_mock.before-renumber.json`): BBC1 101, BBC2 102,
  ITV 103, Channel4 104, Sky One 106, Sky Movies 301 (Sky's 2002 movie block); radio 800-817.
- TYPED NUMBERS FIXED (`150e4fd`), measured on hardware: the 0xB1 entry's last field is
  number<<4 | four flag bits; bit 3 = selectable by typing the number. We sent 6 (bits 1,2) so
  every typed number said "Channel Unavailable"; with 0xE typing 103/104/301/805 tunes ITV,
  Channel4, Sky Movies, Groove Classic. Field 4 is the number the box displays (offsetting
  field 5 by 500 left the banner on 801). Bit 0: no visible effect found. Channel Builder now
  refuses a duplicate number; playout logs a warning for one.
- REMINDERS still refused ("The reminder can't be set for this programme") even an hour ahead,
  with flags 0xE and 0xF. The message is the Guide's own string (RAM 0x804754CD = globals base
  0x8045CB64 + 0x18969, loaded by o-code at 9FC7A04D). Just before, the o-code calls native
  (12,0x16) = 800C66D0, which fetches a programme's stored details by handle
  (group<<12 | index into the request table 0x80165048) and fills a details struct
  (800C9F58 copies the stored record's fields). Next: find which details field the o-code
  tests - candidates are the title record's genre/flag bytes (we send 00 00 00 after start and
  duration) and the event id scheme. Decoding needs an o-code trace: the reference
  disassembler (`re/reference_goretrotv/tools/ocode-disasm.py`) wants a bytecode-trace CSV.
  User: reminders worked on an earlier build.

## Session 17 Nov 2026 - cleanup and v0.7.7-rc1

- Cleanup: the uncommitted v0.7.6/0.7.7 work was committed (`be64fa9`). `.gitignore` now keeps
  local evidence (`re/deployment/`, captures), Ghidra/decompiler text (firmware-derived),
  sim/Quartus output and per-build launchers off GitHub; a merged ignore line was fixed. The six
  build copies beside the project (`Pace2500N_build070`-`075_scaler`) were moved to
  `Downloads/Pace2500N_old_builds/` (nothing unique except the scaler experiment, now
  `re/experiments/ascal_hdmi_line_register.patch`). Delete that folder when no longer wanted.
  An empty stray file `R:fpu_fpga.txt` (from a broken redirect) is still in the project root -
  the safety check would not let the agent delete it; remove it by hand.
- Builds now happen in the project folder (no more copies): recipe in README "Building the
  core". v0.7.7 = MP2 decoder recovery on top of v0.7.6: seed 4, fitter combo logic off.
  81% ALMs, 57% block RAM, 91% DSP. Setup slack: core clocks all positive (worst +0.965 ns),
  HDMI scaler -2.280 ns (known, CRT unaffected; v0.7.4 shipped at -1.946 ns). Hold positive.
  Compressed RBF `Pace2500N_V077.rbf` SHA-256
  4b2d73634f2e90aeadb270179f4c6cfc28daa0dcafced2113ba9b2bfaa0dd75b. Contains no firmware (the
  release top never instantiates pace_bootrom; rom/bootloader_words.hex absent).
- Hardware check of V077 (MiSTer, new relay with the LB1 letterbox flag installed; v0.7.5 relay
  kept as `pace_live_relay.py.v075`): boots to the Guide with the sky guide logo and gradient
  and Guide music on 11778; first All Channels visit filled within 45 s incl. radio titles;
  BBC1 picture and sound, 782 kB/s for 60 s with 0 ring underruns; TV Guide mutes the channel
  and starts music ~10 s later on 11778, Sky returns to the channel; Music & Radio 800 played
  (audio 0x4700) with 0 underruns over 30 s. The MP2 recovery itself is simulation-verified only.
- Known issues carried into rc1: typed channel numbers still give "NNN Channel Unavailable"
  (README corrected - it claimed they worked); the user's line-up has Channel4 AND Sky One on
  106, which shows two "106 Channel4" rows, the second stuck "searching for listings" (the app
  should refuse or warn on duplicate numbers); first Guide music after boot ~10 s.
- The RC app was built into `dist/rc` (the running production app untouched) and smoke-tested
  in portable mode on port 8251 (playout up in ~6 s, service mapping and now/next for all six
  channels). The packaged `--selftest` waits only ~15 s and gives up before a slow line-up
  load finishes - lengthen it.

## Audio decoder recovery

- The user reported a prolonged audio cutoff around loud material. A live
  Sky Movies transport capture decoded cleanly on the PC and peaked at about
  -12.6 dBFS. The FPGA decoder model could play a synthetic near-full-scale
  stream. A damaged MP2 frame reproduced a separate persistent loss of PCM.
- When the parser read past a frame's declared end at a non-byte offset, the
  byte-wise sync hunt continued at that offset. The fix re-aligns before the
  hunt and uses the modular distance to the end of the frame, including when
  the 32-bit bit counter wraps. The error flag remains sticky for diagnostics.
- Two 192 kbps, 48 kHz test streams with one corrupted allocation field lost
  PCM for the remaining 2.1 seconds with the old decoder. The patched RTL
  resumed in about 74 ms and 54 ms respectively. The shorter-PES and larger
  PCM FIFO experiments were dropped. They did not improve the real capture.

## 4:3 letterbox and portable installation

- The MiSTer OSD's `Widescreen on 4:3` option reports status bit 6 in an
  optional `LB1` extension to the live-ring status block. The relay requests
  letterboxing per video tune. Playout fits the stream's display aspect,
  including anamorphic sample aspect, into the 720×576 4:3 PAL raster. The
  Guide and radio stay on their existing audio and transport paths.
- A packaged `portable.flag` keeps the app's settings, Plex sign-in, lineup
  and cache in `data` next to the executable. In-folder settings paths are
  relative. The normal app still uses its existing per-user settings path.
- The private kit's Windows installer copies the app and seeds missing data
  files. Its MiSTer SD tree includes a Scripts entry that asks for the server
  address and installs the relay. The required hardware files are
  `FLASH_U202.bin`, `RAM.bin` and `STATE.bin`. Keep those and the private zip
  out of Git and public releases.
- The private v0.7.6 package is in Downloads. The compressed core was built
  with Quartus 17.0.2, seed 4 and combo-for-area off. CPU setup slack was
  +0.698 ns. Letterbox mode delivered 72-line bars for 16:9, 124-line bars
  for 2.35:1 and full height for 4:3 in the decoded live MPEG-2 test. The
  portable app passed a smoke test from a separate folder, and the installer
  copy test preserved an existing lineup.

## Session 15 Nov 2026 - Plex audio and Info

- Plex's media URLs returned 404 before decoding. `checkFileAvailability=1`
  confirmed that all 32 imported Green Wing and Spaced items referenced
  unavailable files on the Plex server's Q: drive. Four of the 77 imported
  Red Dwarf entries referenced missing files in an older J: folder. The other
  73 had an accessible version. The app now skips unavailable media when
  probing, tries alternative versions for the same Plex item, and avoids
  reporting normal playout socket shutdowns as errors.
- Red Dwarf's first audio track is Czech on multiple episodes. Audio selection
  prefers an English programme track and falls back to available programme
  audio. Verified decoding the English stream on two Plex episodes, including
  the episode used in the MiSTer check.
- DVB present/following EIT supplies Info while tuned. TV gets the Plex episode
  synopsis. Radio gets the stream's `icy-description`, or the SomaFM blurb
  carried in `icy-name`. On hardware, Info showed the Red Dwarf episode
  synopsis in All Channels and while tuned. Drum and Bass UK Radio showed
  its station description while tuned.
- Ghidra confirmed that `800C9CA0` handles a type-2 OpenTV synopsis request
  by matching listing ID, MJD, block and event ID before decoding descriptor
  `0xB9`. Live BBC2 Info showed request type 2 go from `0x3EA` to `0x3EC`.
  The Music & Radio grid uses a station-specific Info popup. It showed the
  track and issued no type-2 synopsis request. Adding the description to the
  SDT row text did not change the popup. The tuned Info overlay shows it.

## Session 14 Nov 2026 - internet radio

- Music & Radio uses private SDT descriptor `0xB2` with genre 4. Numbered
  DVB audio services have type 2 in BAT/SDT and audio-only MP2 PMTs on
  12207 MHz. The Guide and its background music still use 11778 MHz.
- The relay forwards live radio from the firmware's audio route on
  PIDs `0x0700–0x0763`. PC playout transcodes the selected public stream to
  48 kHz stereo MP2 at the television loudness target. Channel Builder saves
  stations in the line-up's `radio` array. The preset list is opt-in.
- v0.7.4 displayed stations 801–809 in the firmware's Music & Radio grid.
  The tuner held lock on 801 for a 70-second run and switched to 802 via the
  grid. A ring capture from the installed setup contained decodable stereo
  MP2 at 48 kHz on `0x0701`. The box returned to BBC1 from All Channels and
  resumed Guide music on re-entry. Local screenshots and ring telemetry are
  in `re/deployment/radio/`.
  The installed Channel Builder and relay were updated. The active line-up
  has all nine starter stations. No FPGA rebuild is required.
- Early guide acquisition is deferred. Radio listings use a generic
  `Live Radio` title when there is no current track metadata or when browsing
  future slots. v0.7.5 reads `StreamTitle` from ICY metadata off-air and
  updates the current half-hour's OpenTV titles plus the SDT current title.
  The live test showed all nine tracks in the Channel Builder Music & Radio
  tab and the MiSTer grid. Reopening the grid picked up new tracks. The
  firmware can keep the previous titles while the grid is open.

## Session 14 Nov 2026 - 0.7.4 live playout and first-open listings

- Hardware validation used the local MiSTer. The user confirmed that the compressed
  `Pace2500N_V074.rbf` and `Pace2500N_V074_Live.mgl` show the blue gradient and
  corner Sky Guide logo and behave like 0.7.1. Sky One ran on the hardware for
  over three hours across programme and break boundaries, ending when the core
  was deliberately reloaded for the listings measurements. 0.7.1 is the fallback.
- The 0.7.2 trace showed tuner lock dropping before the firmware cleared its
  A/V routes while transport bytes were still advancing. The ten-second cycle
  was the firmware retry. The compressed 0.7.3 test stopped with E2 at
  `0x80024831` in the serial interrupt path, with invalid frame length reported
  by the FPGA serial model. The first 0.7.3 test also had an RBF packaging error.
  0.7.4 uses the 75 MHz CPU clock, preserves raster timing during the MPEG
  decoder soft flush, completes outstanding DDR bursts, and keeps artwork video
  parser events out of the guest MPEG status. A single root cause for 0.7.3
  has yet to be confirmed.
- Build 0.7.4 used Quartus seed 4 with fitter physical combo synthesis and
  combo-for-area disabled. TimeQuest at 100 C reported +0.231 ns CPU setup
  slack and -1.946 ns on the HDMI scaler clock. Hardware validation was on
  the user's CRT. Keep the HDMI timing result with any release candidate.
- The home transponder is 11778 MHz. Guide music continues across Guide,
  listings, Box Office, Services and Interactive. A line-up without an audio
  file still tunes to 11778 MHz and drops TV audio. The full seven-day schedule
  was seen on hardware through the final 90-minute slot for all four channels.
  The SDT 0xB2 byte at the start of the private descriptor counts six-hour
  blocks from the current block.
- 0.7.4 can populate All Channels on its first cold visit without a second
  keypress. The baseline test took about 50 seconds after Select at roughly
  28 seconds after launch. Once acquired, the TV-to-Guide grid displayed all
  four rows in the first two-second capture. A faster SI carousel fetched the
  NIT, SDT and initial title filters around five seconds sooner, but a roughly
  30-second guest wait still separated the initial title filters and the
  normal 11778 MHz acquisition. With no keypresses after loading the core,
  the guest tuned to 11778 MHz by about 75 seconds in one run. First-ever
  All Channels at 84 seconds showed all four rows in the two-second capture.
  Changing the transport IDs or the home-service linkage did not shorten
  the cold wait. Evidence is in `re/deployment` locally. The
  October 2002 reference opened Sports around 16 seconds into the clip,
  displayed names around 17 seconds and titles around 19 seconds.
- Production runs Channel Builder playout on the PC at port 8250 and the
  ARM-side relay at `/media/fat/linux/pace/pace_live_relay.py`. Use a second
  test server on 8251 and restore the production relay after A/B tests.
  The running Windows app uses the existing Pace2500N settings and line-up.
  The updated app passed its packaged self-test against a copy of the
  settings and is running from the existing `dist/PaceChannelBuilder`
  folder on port 8250. The tested executable was installed after the old
  process exited, and the relay resumed Sky One. Keep local firmware,
  media, credentials and deployment captures out of Git.
- The updated carousel repeats PAT/PMT every 200 ms, the service tables
  every 600 ms, and today's listings about every second. Three wraps
  recovered all 189 home sections with valid CRCs and zero continuity
  errors through the live multiplexer, including all seven guide dates.
- Repeat test with the released playout showed the first grid still searching
  42 seconds after Select and fully populated at 52 seconds. The local-file
  control loaded all transport data before CPU resume and reproduced the
  same frontend milestones as live playout: state 7 and NIT acquisition at
  about 42 seconds, command 5 at about 63 seconds, and the normal tune at about
  74 seconds after launcher invocation. The updated app and network are
  therefore not responsible for that interval. Ghidra resolves frontend
  command 5 to the mailbox write in `0x8002FD68`, called via `0x8002F474`.
  An alternate checkpoint with installed receiver settings (DTON/DTTS/INST)
  took command 6 into a different scan path and had no lock within 95 seconds.
  A disposable flash copy shortening five 20-second OpenTV timer constants
  left the normal tune at 74 seconds. Shortening the separate 50-second
  retry timer to 35 seconds moved the tune only about one second. Read-only
  RAM sampling showed frontend task state 7 and its acquisition flag set
  through the long pause. Trace the native client that publishes or stops
  that frontend state before testing more table or timer changes.
  The stock flash, checkpoint and launcher remain the hardware baseline.
- PC playout now applies FFmpeg loudness levelling to both Plex and local
  sources. Channel target is -24 LUFS, Guide is -34 LUFS, true peak
  target is -3 dBTP before MP2 encoding. In the October 2002 clip the
  channel excerpts measured -24.9 and -24.4 LUFS and the very quiet Guide
  interval measured -48.7 LUFS. The source 2002 MP2 averaged -11.2 LUFS.
  The Guide target keeps music audible in the live mix. The four 24-second
  PC transport captures measured -25.1 to -23.6 LUFS. Guide measured
  -34.3 LUFS. Sources without an audio stream retain the silence fallback.
  On MiSTer, the audio test held one home transport session with its music
  flag across All Channels, Box Office and Services. TV playback resumed
  after leaving the Guide. Evidence is in `re/deployment/*pace074-level*`.
- TimeQuest traced the 0.7.4 HDMI setup violation to the bob-deinterlacing
  line selection and stride multiply in `sys/ascal.vhd` (`o_vacpt` to
  `o_adrs_pre`). A separate fit in `../Pace2500N_build075_scaler` tests
  registering the selected source line ahead of the multiply. Seed 4 passed
  HDMI at +0.112 ns but missed a CPU setup path by 0.329 ns. The 0.7.4 release
  uses the original hardware-tested core, as requested.
- Published [v0.7.4](https://github.com/retrorepair/Pace2500N-MiSTer/releases/tag/v0.7.4)
  at source commit `31ee306`. GitHub asset digests matched the local archives,
  and the RBF digest matched the copy on MiSTer. Production port 8250 and the
  MiSTer relay use the released playout code. The cold acquisition is still
  open, followed by Information-button Plex synopses and the app workflow.

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
- 13 Nov, user (hardware, by ear): the Guide music PLAYS. Problems: it takes 6-10 s to start,
  and it starts from the beginning of the track every time - it should loop and, like the
  channels, play from the point the wall clock says (as if it had been broadcasting all along).
- 13 Nov, user photo of a real Guide (TV GUIDE main menu): top-left shows a "sky guide" logo
  (white "sky" over "guide" on dark navy), and the menu sits on a light-blue GRADIENT picture
  with white diagonal swooshes, not a flat light blue. Dark navy bands top and bottom as ours.
  Reading: the logo corner and the gradient are a still picture on the VIDEO plane showing
  through transparent OSD areas (we show flat colour). Candidate source: an MPEG still
  broadcast on the home transponder, named like the music by an SI linkage - native (12,0x25)
  looks up linkage type 0x94 (to check).
- Music start fixed 13 Nov: the relay no longer holds the old stream for 5 s after a RETUNE (only
  within one transponder), PAT/PMT go every 200 ms, and the music joins the looped track at the
  wall-clock point. Measured: retune 2-4.5 s after the TV Guide key (the firmware's own delay),
  music requested the same second.
- Background/logo leads (13 Nov): our flat light blue (menu area) and the dark-navy logo corner
  are both OSD-drawn (rtl/pace_video_mix.sv shows video or black wherever the OSD key is
  transparent, and we see neither). So on a real box the gradient + logo are either the OSD
  blended over a video-plane still (our mix is binary key, no alpha) or bitmaps we never
  receive. Native (12,0x25) = linkage 0x94 lookup is called from Guide o-code 9FC69274 and
  9FC69C30 (result stored at Guide global 0x2BCC8, compared against 0x13650/0x1364C) - the
  0x94 linkage is the next thing to identify (a stills/background service is a candidate).
  Also check the OSD descriptor's per-region alpha/blend bits and the "image" device.
- User's plan for the background/logo (13 Nov): they may also have been broadcast or downloaded.
  FIRST prove we definitely do not have them (firmware/flash/Guide resources, and what the
  firmware asks for to draw that corner and the backdrop). Only if they are not in the box:
  recreate them from screen grabs and YouTube videos, cleaned up as far as possible, and
  deliver them the way the box expects (as a broadcast service if that is how it came).
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
