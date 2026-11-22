# Expansion plan — 21 November 2026

This plan incorporates the supplied `EXPANSION_HANDOFF.MD`. Its conversation
archive records the desired experience; its protocol examples are proposals to
verify, rather than established behaviour of this U202 firmware.

Firmware execution stays in the FPGA. PC/MiSTer Linux helpers may generate the
broadcast, supply data or emulate external peripherals. They do not replace the
firmware's CPU, menus, interpreter or PIN decisions. Use local test content and
local simulated orders throughout development.

## Current work and build scope

- V080A is live: original firmware, EEPROM and liveTS suffice, without RAM or
  CPU-state checkpoint. All48 non-HDMI timing checks pass. Z's native RAM-backed
  image plane restores both Guide background and corner logo after liveTV.
- Fixed Teletext page100 body/colours decode on the user's Sony over the existing
  MiSTerPi analogueIO/SCART cable, taking about20s to stabilise. Improve reception
  speed/reliability first; page888 subtitles follow that work. V079Z is fallback.
- Keep slow startup on the active backlog. Measure boot/image/menu readiness
  separately from deliberate test-script sleeps before changing CPU/peripheral
  timing. Preserve the working cold handoff and controller/I2C reset fixes.
- After a reliable build, update clean installation instructions and firmware-only
  launchers. Preserve the earlier priorities for playout stability, audio levels,
  metadata and a robust portable PC app. This expansion does not silently replace
  that backlog. Public release follows hardware validation.

## What can be added cheaply

There is no missing keyboard mapping to bundle: F8/T already send Text, R/G/Y/B
send the coloured buttons, F4 sends Interactive and F2 sends Box Office
(`rtl/pace_keyboard_remote.sv`). Test these through the existing RP2040 mapper.

The best small next addition is an **offline Teletext transport fixture**, using
the server's existing TS/PMT infrastructure. This needs no FPGA rebuild. Start
with one deterministic local page and a disabled-by-default configuration option.
It will prove transport and firmware requests; it will not by itself make a TV
decode Teletext. Complete the required decoder/VBI path afterwards.

Modem UART tracing and a bounded RX/TX bridge are candidates for a later FPGA
build, once the firmware's actual transactions are known. A synthetic ATR, a
generic success reply or an invented descriptor is not a useful shortcut.

## 1. Teletext / Ceefax

**First milestone:** inject a valid Teletext PID into one test channel and prove
that the correct PMT advertises it without interrupting A/V, EPG or continuity.

1. Use a small local `.tti` service: page100 index,101 project status, then pages
   for channel schedules. Add live news/weather feeds only after the local
   fixture works. Avoid downloading feeds during unit tests.
2. Evaluate VBIT2's existing TS output before implementing another packetizer.
   Its documented formats include T42, raw45-byte packets and MPEG TS with
   optional PCR/PTS; the PID is configurable. See the
   [VBIT2 configuration documentation](https://github.com/peterkvt80/vbit2/wiki/Manual-configuration).
3. Add an optional private-data component to the channel PMT, with a language,
   magazine and initial-page descriptor. Validate against
   [ETSI EN300472](https://www.etsi.org/deliver/etsi_en/300400_300499/300472/01.03.01_60/en_300472v010301p.pdf)
   and the existing SI encoder. The standard defines stream type0x06, private
   stream1 PES and Teletext descriptor signalling; raw42-byte T42 records are
   not complete DVB PES packets.
4. Trace the firmware's selected Teletext PID and B0008xxx accesses. Determine
   whether this firmware renders anything internally or expects VBI output to
   the TV. The attachment's internal-decoder claim is not yet established.
5. For native TV decoding, implement PAL VBI insertion through the actual analogue
   output path and verify on a Teletext-capable display. Do not call an optional
   host/OSD page viewer equivalent to native VBI support. HDMI is not a priority.

### Page 888 subtitles — requested after Teletext is stable

22 Nov progress: user confirms stability and prioritises usable text/Teletext,
NO OCR. V080B implementation is prepared and digitally tested: transport-fed
FPGA VBI, timed888 cues, live index/clock, now-next listings, BBC headlines,
public-IP weather and official MiSTer Main updates. Actual PlexSRT and IPTV
WebVTT cue extraction pass. Core build/TV overlay validation remain pending.
See LIVE_TELETEXT.md and the newest handoff; the initial sequence below is
retained as the implementation/acceptance checklist.

User requests TV-decoded page888 subtitles for Plex and, when the source permits,
IPTV. Keep this queued after acquisition/reliability improvements: the current
approximately20s stabilisation is unsuitable for timed cues. No subtitle code
has been implemented, and page100 success does not prove subtitle overlay yet.

- **Plex first:** inspect selectable subtitle tracks and retrieval endpoints.
  Start with text-based SRT/extractable embedded text, using the selected
  language (English by default) and cue start/end times. Keep selection local
  to this application's playout session and preserve general Plex settings.
  Plex supports local external and embedded subtitles; see
  [Plex subtitle documentation](https://support.plex.tv/articles/200471133-adding-local-subtitles-to-your-media/).
- **IPTV:** probe each actual source, not its playlist label. Preserve/repackage
  existing Teletext subtitles, including remapping an advertised source page to
  888 when needed. Convert separate text subtitle tracks (e.g. WebVTT) into
  timed cues. Availability depends on the provider retaining those tracks.
  [FFmpeg's libzvbi decoder](https://ffmpeg.org/ffmpeg-codecs.html#libzvbi_002dteletext)
  can decode DVB Teletext subtitles when compiled with that library; verify the
  shipped Windows binary's capabilities before depending on it.
- **Image-only sources:** PGS/VobSub and DVB bitmap subtitles need recognition
  to recover text for Teletext. Treat OCR as a separate later feature; do not
  claim ordinary subtitle decoding yields text. Burned-in-only captions have
  no separate text track. Missing/unsupported subtitles should be stated clearly.
  [FFmpeg's DVB subtitle format](https://ffmpeg.org/ffmpeg-codecs.html#dvbsub-1)
  is bitmap based.
- **Delivery:** one bounded, timestamped cue pipeline to page888 (magazine8,
  page88), with subtitle/overlay signalling, explicit erase at cue end and on
  retune, and appropriate row repetition. Validate signalling against ETSI before
  assigning control bits. Rebase cue times to actual playout/transcode offsets
  and buffering; discard stale cues after reconnect, seek or programme change.
  Extend the real TS/demux/VBI path; keep firmware execution entirely in FPGA.
- **Acceptance:** deterministic timed text fixture over moving RGB video on the
  actual TV, then one Plex title and one IPTV source with genuine subtitle data.
  Verify TV subtitle overlay, timing, cue clearing, retune/reconnect and no-track
  behaviour without disturbing A/V or EPG. Keep page100 available for diagnosis.

### RGB SCART and VBI output options

User specifically wants to retain RGB picture quality. Full colour CVBS is not
required for Teletext: investigate a properly levelled sync+VBI/luminance feed to
SCART pin20 alongside RGB. Existing MiSTer subcarrier mode does NOT carry VBI
payload: local `sys/sys_top.v` routes composite sync on VGA_HS and a colour
reference on VGA_VS. See the
[MiSTer source](https://github.com/MiSTer-devel/Template_MiSTer/blob/master/sys/sys_top.v)
and [SCART interface reference](https://www.analog.com/en/resources/design-notes/a-single-scart-interface-for-video.html).

Preferred route (user clarification): retain RGB and replace the signal on the
connection currently used for CSync with **monochrome composite containing
sync and Teletext VBI**. Implement waveform generation and blanking preservation
in core/FPGA `sys` logic; MiSTer Main changes are only needed for optional mode
selection/configuration. The present VGA_HS is a one-bit digital output, so
software/RTL changes alone do not establish correct sync/black/white analogue
levels. Evaluate a suitable output stage or an available video DAC plus cable
routing to the sync connection before promising compatibility with the existing
unmodified cable. TV Teletext support is already understood by the user.

AlternativeA: a CUSTOM mode repurposes spare VGA_VS for timed Teletext data and
uses a suitable external level-setting/combining circuit with VGA_HS composite
sync to feed TV pin20. This replaces the colour-reference function; it is not
available merely by enabling `subcarrier`. Never directly connect two driven
outputs together. AlternativeB: separate monochrome composite/luminance with VBI
alongside RGB, using an appropriate DAC/output path. Confirm existing I/O board,
cable routing, loaded signal levels and the TV's Teletext support on its AV
input before selecting either design. Preserve RGB and sync levels/timing;
verify the VBI waveform electrically and on the TV, not through an active-picture
screenshot. No pin-routing changes are included in Z.

**Acceptance:** correct page100, numeric page changes, colours and rolling updates;
missing Teletext leaves normal TV usable; service/channel switches do not leak
old pages. Ordinary active-picture screenshots cannot prove VBI correctness.

## 2. OpenTV applications / Red Button / Sky Active

**First milestone:** load a minimal application through the real firmware's
download path, show a line of text, accept a coloured key, and exit to TV.

- Reuse `tools/opentv_natives.py`, the existing o-code RE and TS generators.
  Earlier project RE identified the0x92 linkage/download-transport path; use
  that evidence to locate the directory, module and launch parsers.
- Establish the firmware's exact application signalling and carousel format
  before choosing DSM-CC tools or adding descriptors. Test module versions,
  partial reception, missing modules, retries and clean application teardown.
- The supplied0x6C/0x6E descriptor examples are not validated Sky signalling.
  In standard DVB SI they name cell-list and announcement-support descriptors;
 0x6F is application signalling. Neither that standard tag nor a guessed private
  tag proves what this OpenTV build accepts. See the descriptor registry in
  [ETSI EN300468](https://www.etsi.org/deliver/etsi_en/300400_300499/300468/01.05.01_60/en_300468v010501p.pdf).
- Prefer a known compatible preserved application/carousel or a documented
  minimal test module. Do not make an unavailable SDK a hidden installer
  dependency or assume generic carousel tools produce compatible o-code.
- Once loading works, add a secondary versioned data module for local weather,
  headlines and read-only Home Assistant status. Add controls only with explicit
  endpoint configuration and user-selected actions. A preserved game is a later
  compatibility test, not the first transport test.

**Acceptance:** firmware-created prompt/menu, real key events, versioned updates,
safe return to TV and no permanent stall when data is absent.

## 3. Virtual modem / local online services

**First milestone:** record the real modem initialization/dial bytes and return
correct basic AT responses through a bounded emulated UART.

- Existing software RE has `tools/pace_external_uart.py`; the FPGA currently has
  a small polling UART subset at B4080000..7, with guest byte lanes XOR3.
  RX, interrupts, carrier state and real modem responses are not complete.
- Use Ghidra and traces to prove modem routing, baud/divisor programming,
  control/status bits and timeout expectations. Do not assume a host device
  named `/dev/ttyS1` already connects to this UART.
- Implement FIFO/LSR/MSR/IRQ semantics and the bridge independently of the debug
  UART, preserving controller-link timing and useful diagnostics. Start with
  loopback and bounded AT handling, including hang-up, reset and no-carrier.
- Only after `CONNECT`, inspect the actual data protocol. PPP and HTTP are
  hypotheses until observed. If PPP is confirmed, use a private local endpoint
  and constrain DNS/portal services to that link. Do not alter the server's
  general Plex, DNS or network settings.
- Capture requested resources and serve a small compatible local portal. Then
  consider a Plex request/search interface, RSS reader or retro mailbox.

**Acceptance:** successful native connection and disconnect, timeout recovery,
no external phone service dependency and no unrelated network configuration change.

## 4. Viewing card and local parental PIN

**First milestone:** native card presence, initialization and card identity work
without regressing cold boot; then trace a native PIN request and response.

- The actual project has a framed front-panel/smartcard microcontroller link
  at B2009010 (`tools/fplink_from_mlog.py`). A directly bridged ISO7816 UART is
  not established. Trace card-detect, reset and identity before adding a daemon.
- The attachment's exact ATR, PIN storage location, INS bytes, baud/protocol,
  retry status words and last-four-digits default are **unverified for this
  firmware/card generation**. Generic smartcard conventions do not establish
  the NDS application protocol. Resolve the firmware handlers in Ghidra and
  use observed framing, lengths and checksums.
- Determine the actual OpenTV age/adult flags from its parsers. Standard DVB
  parental-rating metadata is not automatically the proprietary Sky format.
  The current channel genre field is only3 bits with seven named categories;
  do not invent an eighth Adult genre or equate Specialist with adult gating.
- Once protocol and triggers are known, provide configurable local card identity
  and PIN persistence, correct success/failure/retry behaviour, and native PIN
  change support. Do not log entered PINs or acknowledge every command as success.
- Keep the A/V decision in the real firmware and correctly implement its mute/
  blank controls. No real encrypted subscription service is needed for these
  local test programmes.

**Acceptance:** no-card screen, correct/incorrect PIN, retry/lock/recovery, PIN
change persistence, new-event/channel transitions and audio/video gating agree.

## 5. Local Box Office / simulated PPV

**First milestone:** an actual native Box Office event and order/cancel screen
for a locally supplied trailer/movie pair.

- Identify the firmware's Box Office listing, event, price and entitlement
  formats. A PMT CA descriptor alone does not establish the ordering workflow.
  The attachment's CA IDs, dummy ECM PID and purchase APDU need verification.
- Build explicit event IDs, schedule and local prices into test metadata.
  Implement only the card/entitlement responses the native workflow requires.
  Adding CA flags to ordinary clear channels prematurely can break their tuning.
- On a confirmed local simulated order, notify the PC playout service to switch
  trailer to programme. Keep cancel/repeat requests idempotent and handle retune,
  restart and event expiry. Never send a real purchase or billing request.

**Acceptance:** native preview/order/confirmation screens, optional PIN flow,
correct film selection and cancellation, with no charges or external backend.

## Sequence and release evidence

1. Z return-to-Guide validated on hardware; leave it live and retain Y fallback.
2. Measure startup; finish the firmware-only clean-install baseline.
3. Produce the optional Teletext transport fixture and verify firmware routing.
4. Develop the OpenTV carousel fixture and modem/card protocol traces. Choose
   the next small FPGA bridge from that evidence, rather than enabling all
   peripheral guesses in one build.
5. Complete card/PIN and Box Office after the relevant native paths are proven.

Keep one agent and one fitter. Record source/build hashes, timing (including
experimental misses authorised by the user), original-flash checks and real
screenshots. A transport fixture, a simulator success and a visible native
hardware feature are distinct milestones. Update this plan and `handoff.md`
with concrete results before announcing features or making a release.

Resource note: Z uses110/112 DSP blocks,444/553 RAM blocks and89% of ALMs.
Prefer PC transport work and the existing firmware interpreter for expansion;
check logic/memory/timing costs before bundling more FPGA peripherals.

## Unchanged-wiring experiment (hardware identified)

User reports MiSTer Pi analogue I/O and standard SCART wiring. Reference A/V1.2
schematic shows HSync and VSync each pass through100ohms, separately from the
ADV7125 RGB DAC. Exact cable attenuation is still unmeasured; standard wiring
alone does not establish resistor values. Do not state this reference is a
verified schematic of every Retro Remake revision.

For nominal PAL video, desired levels at the75ohm input are sync-tip0V,
black/data-zero0.3V and SystemB Teletext data-one approximately0.762V
(0.3+0.66*0.7; ITU-R BT.653-3). With3.3V GPIO,100ohm board resistance and an
EXAMPLE470ohm cable resistor, the two DC levels are0V and0.384V. Simple NRZ
Teletext on HS therefore cannot create the nominal three levels.

An unchanged-wiring experiment could use high-rate PWM/pulse-density modulation
and the receiving analogue bandwidth to synthesize an intermediate black level.
Using black=0.3937*the available high and data-one=available high preserves the
nominal Teletext/sync amplitude ratio at reduced overall level; with the example
above that is0/0.151/0.384V. Acquisition depends on TV gain/sync thresholds and
filtering; no success or standards compliance is established. Keep output drive
and peak voltage unchanged, preserve PAL sync timing, default to ordinaryCSync,
and start with a separate fixed-page100 test rather than speculative live data.
V080A now implements this as an optional, labelled fixed-page100 output test.
Digital waveform simulation and independent libzvbi page decoding pass; Quartus
all48 non-HDMI timing checks and repeated190s hardware tests now pass. Exact
flash, CPU health, packet progress,30s timeout/manual cancel and unchanged RGB
are verified; outcomes are recorded in handoff.md. User CRT photo now confirms
body text and colours decode on the existing MiSTerPi analogueIO/SCART setup,
after about20s of repetition to stabilise. Next investigate acquisition speed
and reliability; do not extrapolate universal TV compatibility or analogue
standards compliance. F11 starts/cancels a30s window; ordinaryCSync is the default and timeout
state. See TELETEXT_TEST.md. Live broadcast Teletext routing remains later work.

If that receiver-dependent experiment fails, use a small weighted-resistor
sync/data combiner from HS and a spare VS output, or a suitable DAC/output-stage
route. Include existing board/cable resistances and75ohm termination when sizing
it. Do not directly tie GPIOs, bypass attenuation, or give solder values before
verifying the actual cable. RGB remains untouched; no board surgery is required
merely to design a cable-side adapter.
