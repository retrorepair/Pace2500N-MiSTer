# Pace 2500N / Sky Digital MiSTer FPGA â€” Project Handoff

**Continuation:** Read `CURRENT_STATUS.md` first for later fixes, measured
Quartus results and HDL regressions. The latest session is directly below; the original
7 Nov snapshot further down is retained for history only (it predates everything that works).

## 21 Nov 2026 - Physical CRT Teletext body and colours CONFIRMED; acquisition about20s

- User reports: "It took about20 seconds of the page repeating to stabilise
  but it works." Second CRT photo shows page100 header AND multiple body rows
  with cyan/white/green/yellow/red text matching our fixture, including PACE
  2500N/MISTER, HSyncPDM experiment, decoder confirmation and F11 instructions.
  This supersedes the header-only observation below. Actual TV body reception
  is established on this Sony with existing MiSTerPi analogueIO/SCART wiring.
- Keep scope precise: reception demonstrated on ONE setup after about20s;
  not an error-rate measurement, fast acquisition, universal compatibility or
  proof of standards-compliant analogue levels. Still a fixed output fixture,
  not broadcast/TS Teletext or firmware-controlled page delivery.
- Next VBI priority: diagnose/improve acquisition while preserving RGB/native
  firmware stability and existing wiring. Do not assume whether erase-page
  cadence, sparse one-packet/field transmission or analogue filtering/gain is
  responsible without a discriminating test. Nominal carousel is0.5s, but
  observed stabilisation is about20s. Existing30s test window is quite short
  relative to that observation; consider a longer temporary window next time.
- No new code, key injection, reload or Quartus build for this observation.
  Photo retained only in local ignored evidence; documentation pushed to the
  cold-boot branch under the user's existing GitHub backup instruction.

## 21 Nov 2026 - User photo confirms TV receives page100 header; body reception pending

- User reports Teletext after pressing the Teletext button, with CRT photo
  showing the exact builtin header PACE TEST100 / RGB / VBI TEST. This is
  physical-TV header acquisition through the existing MiSTerPi analogueIO /
  SCART setup. The photo's body is blank: do not claim a complete page yet.
- Read-only SSH check confirms V080A remains live and CPU IR00/HALT00. TT=
  40000000: PAL line lock, temporary test OFF, completed packet counter zero.
  TV may be displaying a header cached during prior automatic test windows;
  this is a hypothesis, not an established cause of the blank body.
- Suggested user test: leave TV in Text mode, press F11 on MiSTer to open a
  fresh30s transmission window, wait a few seconds for rows. Asked whether
  their Text button was TV remote or MiSTer mapper, and whether rows appeared.
  Await observation before modifying waveform or starting another build.
- No FPGA changes, reloads, injected keys or new build during this observation.

## 21 Nov 2026 22:28 - V080A built, deployed and hardware checks PASS; TV decoding pending

- User-requested quiet build observed: no feature work/research during44m09s
  Quartus compilation. User explicitly requested GitHub backup during wait;
  source, prior cold-boot fixes, optional page100 fixture, watcher and handoff
  pushed to existing cold-boot branch in fe90523. No public release created.
- Full compilation completed22:19:30. ALL48 non-HDMI timing checks PASS;
  worst setup+0.266ns, hold+0.256ns, recovery+3.576ns, removal+0.671ns,
  pulsewidth+0.370ns. HDMI excluded as requested. Fit37532/41910ALMs(90%),
  446/553RAMblocks(81%),110/112DSP(98%): only96ALMs+2RAM overZ, no addedDSP.
- Uploaded RBF hash verified locally/remotely:
  c12db1c5a599847881ab644367d7eaa8a0dade89227ed36c3ec357dcea7f308e.
  Firmware unchanged32f6b2e84d0c4c4ec280a72f2d080e4b6fa5e68e8438ef712f34f97f63d38c7f.
  MGL loads original FLASH_U202, EEPROM and liveTS only, NO RAM/STATE image.
- Watcher first190s capture V080A-221935: hardware checks passed but my Python
  verifier raised KeyError on one UART-corrupted RET field. Restore trap
  successfully returned toZ. This was a TEST-PARSER error, not a CPU halt.
  Fixed parser: require complete snapshots, report malformed count, reject
  excessive corruption and any readable HALT even in a malformed frame.
  Regression preflight verifies isolated corruption accepted/reported and an
  injected HALT=E5 in that malformed frame rejected. Also fixed scp directory
  copy (OpenSSH rejected remote/.). No FPGA rebuild or CPU changes needed.
- Repeated complete190s hardware test V080A-222357 PASS; originalflash all
  262144qwords exact, IR00/HALT00 and continuing retirement, PAL line lock,
  packet rate50/s (250 over5s sampled span), automatic30s expiry and manual
  cancel. First capture's automatic window emitted exactly1500 packets.
  UART malformed snapshots reported1/83 first,2/83 repeat, not silently hidden.
  Full evidence downloaded to local re/deployment/coldboot_20261121 and SD.
- Native720x576Guide screenshot before/during/after first test is PIXEL-IDENTICAL
  (PIL difference bboxNone), including background and upper-leftSkyGuide logo.
  This proves FPGA RGB is unchanged; SSH screenshots CANNOT see the TV's own
  Teletext decoder. Physical-TV acquisition remains UNPROVEN until user tests.
- V080A confirmed LEFT LIVE on192.168.1.103, experiment OFF/ordinaryCSync.
  User controls: F11 starts30s window, TV's own remoteText then100; F11 cancels.
  F11 can be mapped on user's USBRP2040IRadapter. Test is builtin labelled
  fixedpage100, not live broadcast Teletext. TELETEXT_TEST.md has instructions.
- V079Z remains fallback. Startup delay still unfixed; expansion liveTTX/OpenTV/
  modem/card/BoxOffice and earlier backlog remain per EXPANSION_PLAN.md.

## 21 Nov 2026 - V080A fixed page 100 prepared for quiet build/watch/deploy/test

- User requires build time be QUIET: finish code/tests/scripts/docs first, start
  one frozen build with automatic deploy/test watcher, then wait without other
  work. Tell user when starting. One agent, one fitter; no public release.
- Implemented optional PACE_TELETEXT_TEST module/sys hook: RGB/VS/audio/drive
  unchanged, F11 temporary30s HSync PDM experiment, immediate F11 cancel,
  default normal CSync. Only native54MHz625-line RGB+CSync; mode/rate/missing-HS
  guards. Peak voltage/attenuation unchanged. Physical TV decoding unproven.
- Built-in labelled PAGE100 fixture (25x45bytes), SystemB6.9375Mbit/s via37/288
  NCO; packet starts555clocks after HS on a VBI line, LSB-first55/55/27 prefix,
  Hamming8/4 headers and odd-parity text. No transport/backend/network needed.
- Simulation PASS55 serialized physical-output packets, both fields, PDM density,
  start/cancel/scaled timeout, bad/missing HS and bit-identical inactive CSync.
  Independent unmodified Ubuntu libzvbi0.2.42 decodes page100/text correctly.
  UART all8 optional-field combinations PASS; full core optional-port lint PASS.
- TELETEXT_TEST.md contains user controls and limits. Lab watcher/scripts in
  re/deployment/coldboot_20261121; frozen source snapshot created at
  %TEMP%/Pace2500N_cold_ttx100_20261121, seed6, Z CPU/PLL unchanged. VersionV080A.
  Watcher must hash upload, check flash/IR/HALT/retirement/PAL lock/packet rate,
  auto timeout/manual cancel, leave test OFF on success or restoreZ on failure.
- V080A build/watcher STARTED; no further feature edits during compilation.
  User subsequently requested pushing current source/handoff to GitHub while
  waiting. Backup goes to existing cold-boot branch, including prior uncommitted
  cold-boot/image-plane fixes and tests; ROMs, RAM/STATE, large traces and private
  captures remain local. Four Huffman flash/legacy-RAM compatibility tests PASS.
- Build/hardware outcomes pending below; do not call TV decoding proven from
  FPGA screenshots. Z remains working fallback; startup speed still unfixed.

## 21 Nov 2026 - VBI electrical feasibility follow-up

- User asks electrical changes and whether to try as-is; hardware now identified
  as MiSTer Pi analogueI/O with standardSCART wiring. ReferenceAV1.2+IO9.2
  schematics downloaded to %TEMP%/pace_vbi_electrical, rendered/inspected(page1
  is schematic;pages2/3 arePCB). HS/VS each100ohms in reference, RGB hasADV7125;
  HS is not DAC output. Exact RetroRemake revision/cable resistor not verified.
- SystemB data-one66% of black-to-white excursion (ITU BT653), giving nominal
  sync/black/Teletext-one0/0.3/0.762V. EXAMPLE3.3V+100board+470cable into75ohms
  gives high0.384V. Raw HS bits cannot supply all3 nominal levels.
- Optional unchanged-wiring PWM/pulse-density test could generate intermediate
  pedestal at lower overall amplitude (example0/.151/.384), relying on TV gain/
  filtering. Preserve drive/peak levels; separate fixed-page100 fixture first,
  normal CSync default/return. Not implemented/deployed, no compatibility claim.
- Conventional fallback: weighted resistor summing HS+spareVS data (one extra
  conductor/smalladapter), or DAC output stage. Values must include real cable
  and board resistance, not just assume470ohms. EXPANSION_PLAN.md updated.
- Stable working Z remains untouched/live; no new Quartus build started.

## 21 Nov 2026 21:03 - Z native RAM image plane HARDWARE PASS, restoring backdrop/logo after TV

- Z compiled20:55:41, then compressed/uploaded/hash-verified. RBF SHA256
  c47bc254fb23fd319298b8ba1561a97d30cff5489c0cd9c40dd55f7bcdeb017d.
  All48 non-HDMI timing checks evaluated;47 pass, CPU1x hold-0.210ns remains.
  User explicitly authorised trying timing-missed builds; this is EXPERIMENTAL,
  not a fully timing-clean release. BaselineY remains available with all48pass.
- Standard160s test V079Z-205546 PASS: native Guide/background/logo, flashall0,
  IR00/HALT00; actual capturedRAM all622080 samples within1 of independent YUV
  reference without correction. Full evidence local+SD, core/RAM hashes saved.
- Scripted175s repeat V079Z-nav-205841 PASS: Guide -> All Channels -> Info ->
  playingBBC1 -> Guide. Return screenshot210106 has BOTH backdrop AND Sky Guide
  cornerlogo. Pixel comparison to FIRST Guide205710 is IDENTICAL (ImageChops
  difference bboxNone); white logo632pixels in ROIx30..135,y40..105. Do not be
  misled by small preview thumbnails: logo is present and pixel-identical.
  UART ends IR00/HALT00, WD05052601 (decoder no longer live). Thus image comes
  from actual guest RAM-backed plane after TV, not a retained decoder frame.
  ReturnRAM stillall622080 samples match original reference within1, proving
  native cached buffer survives TV. Flashcheckall262144 qwords matchoriginal.
- Test trap restoredY as designed. Third Z run exec87084 now leavesZlive: SD
  .../Z-left-live/uart.txt and flashcheck.txt,120s monitor, F1 after65s, screenshot
  coldZ-left-live. COMPLETED: flashall262144 qwords match, IR00/HALT00 at120s;
  remote MiSTer process confirms V079Z loaded and left active for user.
- Z fit37436/41910ALMs(89%),444/553M10K(80%),110/112DSP(98%). Expansion planning
  must respect remaining2DSP: prefer transport/firmware applications or LUT logic,
  not more arithmetic-heavy pipelines. No CPU or PLL changes in image-plane fix.
- Slow startup is NOT fixed. Next work: measure genuine readiness phases vs test
  sleeps, then expansion milestones per EXPANSION_PLAN.md (all5 requested areas
  saved; preferred Teletext route RGB plus monochromeCVBS/VBI on syncconnection).
  No public commit/push/release made. No RAM/STATE in any new cold MGL.

## 21 Nov 2026 - Clarified preferred Teletext output

- User already understands HS/VS/subcarrier and TV Teletext requirements. Their
  preferred topology is RGB unchanged plus MONOCHROME COMPOSITE WITH VBI on
  the existing CSync connection. Agreed this is the preferred output signal.
- Implementation belongs in core/sys FPGA waveform and blanking logic, with
  Main changes only for optional configuration. Existing HS pin is one-bit GPIO;
  correct3-level sync/black/white needs a suitable output stage or DAC routing,
  not only a Main patch. Record cable/IOboard electrical evaluation as pending.
- EXPANSION_PLAN.md updated preferred route; no Z pin/waveform changes.

## 21 Nov 2026 - User asks RGB/subcarrier VBI feasibility

- Answered: retainRGB; full colourCVBS not inherently needed. Teletext must reach
  TV composite/luma input(SCART20) at proper VBI timing/levels. Current local
  sys_top.v: VGA_HS=composite sync when configured, VGA_VS=subcarrier reference;
  subcarrier itself carries noTeletext. Custom spare-VS data plus proper external
  level-setting combiner with HS is a candidate, not existing feature. Do NOT
  directly tie drivenpins. Alternative separate monochromeCVBS/luma+VBI alongside
  RGB. Need actual cable/IOboard/TV AV-Teletext support and waveform validation.
- Added both RGB-compatible options to EXPANSION_PLAN.md with primary sources.
  Z source remains frozen; no VBI/pin changes were slipped into running build.

## 21 Nov 2026 - Expansion handoff reviewed; roadmap saved

- User supplied EXPANSION_HANDOFF.MD and asked to add its new features to the
  plan/handoff, considering easy additions before another build. Read the whole
  attachment; clean actionable roadmap is EXPANSION_PLAN.md. Z had already
  started, so its frozen source remains unchanged.
- Planned features: Teletext/Ceefax, real downloaded OpenTV/Red Button apps,
  virtual modem/local portal, virtual viewing-card/PIN support, local Box Office
  preview/order workflow. Keep current cold-boot/cache-image fix and startup
  investigation first; preserve previous stability/audio/install backlog.
- Easiest next step: OFFLINE optional Teletext TS/PMT fixture on PC; VBIT2 already
  supports TS output. Actual core/TV display still needs firmware PID routing and
  PAL VBI support or proof of an internal decoder. F8/T Text, coloured keys,
  F2 Box Office/F4 Interactive are ALREADY mapped: no extra FPGA mapping needed.
- Do not implement attachment's speculative protocol constants as facts: standard
  DVB0x6C/6E are not application tags (ETSI EN300468); actual Sky parser needed.
  PIN storage/ATR/INS/retry/baud, adult mandatory-lock claims and PPP/HTTP transport
  remain unverified for this ROM. Existing smartcard controller is framedB2009010;
  modem polling UART B4080000..7 lacks RX/IRQ/carrier semantics. Current genre
  field3bits: do not add invented Adult category8. Roadmap names local code,
  prerequisites, acceptance criteria and primary ETSI/VBIT2 references.
- No expansion feature newly claimed as working; no new build beyond Z. Suggested
  small future FPGA addition is bounded UART tracing/bridge after actual protocol
  capture. Keep firmware CPU execution entirely in FPGA. No public push/release.

## 21 Nov 2026 20:08 - Real RAM-backed image plane implemented; Z building

- Y-left-live completed120s flashall0/IR00/HALT00; remote MiSTer process confirms
  V079Y loaded and left running. This is current baseline, no fitter parallelism.
- Ghidra /tmp/cold_cached_image_registers.txt establishes REAL image registers:
  80009F60 -> B0004004=Yeven,400C=Yodd,4008=UVeven,4010=UVodd;
  4014=(sourceH-1)<<16|(sourceW-1),4034=H<<16|W;80009D1C ->4024 outputsize-1.
  800099B0 writes4000 control07C1C001 when cached plane enabled (bit0=1),
  07C1C000 when disabled. Native3/3F->manager26->provider8002156C invokes these.
  Actual Y and X-return RAM at80109194 holds four pointers A05E9678/A061C078/
  A064EA78/A0667F78,720x576,zero crop; matches these registers. 4034 MUST be
  024002D0, NOT0 (caught during RE review and covered in final test setup).
- New rtl/pace_video_image_plane.sv reads guest unsigned YUV420 planes via8-beat
  shared-DDR bursts into dual-clock line buffers; native4000 enable/readback,
  source/outputgeometry, tagged interlaced lines, BT.601 RGB. Uses ACTUAL cached
  DMA7 image, no host bitmap or fixed guest pointer. Full uncropped720x576 only;
  unsupported profile suppresses output. Pixel chroma index is y/2 so UV field
  selection=y[1], row=y>>2; Y fieldselection=y[0], row=y>>1.
- Drains accepted burst on disable/reconfigure/CPU warm reset. Separate bus_reset
  clears owner epoch only with globalcore_reset, matching main arbiter ownership.
- Integrated readback/ready priority above generic CSRs; isolates4000..4034 from
  their former defaultCSR127 alias. New read owner9, per-owner burst count and
  response demux; OSD retains higher priority. Image RGB/mask has the same3-stage
  latency as OSD; substitutes only clear/background pixels. CPU/PLL unchanged.
- sim/tb_video_image_plane.sv PASS:34560 pixel checks over both fields/fullwidth,
  synthetic unsignedYUV semantic oracle, burst latency/backpressure, TV/disable
  ->new imagegeneration with no stale tags/colour, warm-reset drain, unsupported
  size rejection. /tmp/image_plane_tb.log. Full top lint PASS0errors, no new
  image-plane/UNOPTFLAT warnings (/tmp/image_plane_top_lint.log). Diff checkPASS.
- Z source snapshot %TEMP%/Pace2500N_cold_imageplane_20261121, label0.7.9Z(RAMimage),
  seed6, runner exec47061 build-and-test-z.ps1. One fitter only. Retains allY
  colour/retention/MV fixes and adds image plane. MGL still3 files, noRAM/STATE.
  Auto runner reports all48 non-HDMI checks; per user's explicit instruction,
  timing misses are recorded but experimental deployment/test permitted. No
  release. Standard160s test collectsRAM/UART/screenshots then restoresV079Y.
  cold-nav-test.sh supports Z,175s Guide/listings/info/TV/returnGuide test must
  follow to validate return image; it now also restores Y. Do not claim solved
  on hardware until that return screenshot is observed. No new public push.

## 21 Nov 2026 19:56 - Y completed and hardware PASSES; leaving Y live

- Y runner63203 completed during wait: compilation ended17:40:17,46m51s. ALL48
  non-HDMI timing checks pass, minimum+0.246ns; CPU2x setup+0.993ns. No timing
  exception required. RBF SHA25638709ba07a89b20f939a3d12684ae1208ece0dd4cdb7a158da858022b8bdaa64.
- Auto hardware160s run V079Y-174021 produced native TV Guide/background/logo,
  flashall0, CPU IR00/HALT00, DMA7 completed, image slot1=802AF170/state0. ALL
  622080 captured samples in REAL hardware RAM match independent FFmpeg YUV420
  within1, WITHOUT legacy correction. This validates actual Y pixel conversion.
  Screenshot guide.png now fetched locally. Normal test restored V078 at exit.
- User resumed19:55 after waiting. New Y-left-live run exec9900 loads Y, waits65s,
  flashchecks and opens Guide, records120s UART, leaves Y active on success.
  No new Quartus build running. No public commit/release.
- Ghidra next cached-backdrop return bug: provider pointer literal800570F0 ->
  80105E18 ->800FC520; +120=8002156D,+124=80021A0D,+128=80021709,
  +E8=80021741,+EC=80021915. Manager cmd26(active native3/3F) invokes+120
  with cached-image descriptor, stores handle at80105E74=1 in Y RAM. This is
  promising REAL RAM-backed image-display path, rather than retaining TV banks.
  Read-only decompile pending /tmp/cold_cached_image_display.txt.

## 21 Nov 2026 17:08 - User authorises small timing misses; X works live, cached backdrop remains

- USER STEERING: explicitly try failed builds despite small timing shortfall;
  stop burning tokens while compiling. Experimental hardware tests authorised,
  preserve measured timing failures in evidence. No public reliability claim.
- Manually converted/deployed X despite CPU1x hold-0.060ns; SHA256
  cd0be632035712a8edcf5bcd794db00cc97a3a75aeb76b54021786095b25b13b
  matches remote. First160s test V079X-170016 passes flashall0, IR0/HALT0.
  User interacted during test; Guide screenshot is PERSONAL PLANNER with correct
  background/logo. Preserve this run but do not use it as an automated nav proof.
- Second175s test V079X-nav-170316 is the scripted navigation repeat: real native
  Guide -> ALL CHANNELS on FIRST attempt -> Info -> playing BBC1 -> Guide. No
  CPU halt, flashall0, RAM dump16MiB. Local screenshots +RAM/UART on SD and PC.
  Live-now-170437.png is actual cold-core TV Guide menu, shown to user. X loads
  only EEPROM/FLASH/liveTS, NO RAM/STATE. User also reports it runs well but slow.
- IMPORTANT REMAINING BUG, independently observed by user and captured in
  170540-coldV079X-nav-return-guide.png: after TV, Guide backdrop/logo disappear
  (plainlightblue/blackheader). Retained decoder image was replaced by TV. Need
  restore/display the firmware's CACHED native YUV image on Guide return; Y's
  signed/U-V conversion is prerequisite for valid cached image pixels, but Y
  alone does NOT implement the RAM-to-display restore. Do not claim it fixed.
- Script test restoredV078 at exit. A third X load now leaving X live for user:
  exec from latest tools, UART/flash under SD .../X-left-live, F1 after65s. No
  restore on successful completion. Y runner63203 compiling; fitter95136 at last
  check. If Y timing misses slightly, user authorises manual experimental test.
- Late video MMIO records after80s absent in nav UART (trace overwhelmed/frozen),
  so don't infer register values on return from absence. Native3/3D8005B77C posts
  manager command24;3/3E8005B7AC->25;3/3F8005B7E0->26 per existing decompile.
  Future Ghidra target: cached still-display path and corresponding EMMA pointers.

## 21 Nov 2026 16:56 - X timing rejected; Y compilation started, no X hardware run

- X full compile completed16:53:21,46m03s total. Timing gate found CPU1x hold
  -0.060ns; NO RBF conversion/deployment/test. Watcher72079 exited with error
  as designed, MiSTer remains V078. Separate slow100C detailed report gives
  -0.062ns on write_cdc_data_2x[50] -> mem_dataWrite[50], clocksCPU2x ->CPU1x,
  clockskew0.732ns/data delay0.731ns. NOT the earlier W itagram path. X CPU
  setup+0.650ns. Reports saved locally X-hold-paths.txt and X-timing.summary.
  Do not add false paths or call this a functional CPU fault; route/timing fail.
- Y queued runner63203 started compiling after X master91068 exited, new master
  quartus_sh10392/map49944 at last check. Source frozen, seed6, pixel correction
  plus retention/MV. Y-source-hashes.json saved. Only one fitter at a time.
- Full independent original-flash MPEG->DMA7 test PASS: all622080 bytes within1
  of FFmpeg unsigned YUV420, then retained image survives ES input stop. This
  is semantic pixel coverage, not just comparing against internal signed RAM.
- Native-decoder-field.png is SIMULATION, not a hardware Guide capture. It shows
  correct blue backdrop/logo. W-captured-still-converted.png reconstructs the
  actual old hardware RAM after applying the now-proved format corrections.
- Prepared lab cold-nav-test.sh V079X|V079Y on SD:65s boot, Guide, All Channels,
  info, TV, return Guide;175s UART +RAM evidence, stableV078 restoration on exit.
  Not run yet (X failed timing). Y timing must pass before hardware validation.

## 21 Nov 2026 16:39 - DMA7 signed-sample and U/V-order bug PROVED; Y queued

- Reconstructed W hardware's native image at005E9678 from the four packed planes
  in V079W-160547/ram.bin. Its unconverted unsigned YUV image has wrong colours.
  This is a REAL format bug: prior byte-for-byte decoder-RAM checks mirrored the
  signed internal storage instead of checking the guest image semantics.
- Decoder motcomp_recon.v stores signed -128..127 samples; resample_bilinear.v
  stage6 adds128 for display. resample_addrgen.v STATE_WR_U uses COMP_CR at10000,
  STATE_WR_V uses COMP_CB at14000: the bank names are reversed relative to U/V.
  DMA7 must XOR every component byte with80 and interleave bank10000 U first,
  bank14000 V second. Current rtl/pace_video_capture_dma.sv now does this.
- Independent FFmpeg decode of ORIGINAL16524-byte flash still compared with the
  transformed W hardware capture: ALL622080 samples differ by at most1, mean
  absolute errors Y0.0045/U0.0081/V0.0031. This validates field/raster/bank layout
  and identifies both corrections without relying on a rendered guess.
  New tools/compare_captured_still.py accepts complete RAM, --base0x5e9678,
  --reference raw720x576yuv420p and optional --legacy-signed-swapped for OLD W/X.
  Local private reference-still.yuv/hex, W-captured-still*.png/yuv under evidence.
- Unit memory model now stores SIGNED semantic Y/U/V pixels at decoder's actual
  bank offsets. Fails oldRTL first byte80 vs00 (/tmp/capture_signed_before.log),
  corrected RTL PASS all6 packed/gap planes (/tmp/capture_signed_after.log).
  Integration sim has optional +YUV_REF=hex, compares every written sample with
  independent unsigned reference within1. Runner CAPTURE_REFERENCE enables it.
  PASS all622080 samples within1 plus picture retention at199ms simulated,
  /tmp/capture_signed_integration.log,120s wall. Exec46963 completed.
- X remains frozen in %TEMP%/Pace2500N_cold_picturehold_20261121, compile82147,
  master91068/fit90340, deploy/test watcher72079. X has retention+MV diagnostics
  but OLD signed/swapped capture bytes. It is still useful for decoder-stall RE.
- Y isolated snapshot %TEMP%/Pace2500N_cold_capture_pixels_20261121 copies X and
  only changes capture byte conversion/U-V selection + label0.7.9Y(native pixels).
  Seed6. build-and-test-y.ps1 exec63203 WAITS for X/quartus_fit then compiles,
  requires all48 non-HDMI timing checks pass, converts/uploads/hash-checks RBF,
  and runs SD-backed160s cold-test.sh V079Y (now accepts Y). ONE fitter only.
- Current normal core verified by remote MiSTer process cmdline: V078. Screenshot
  omits HPS OSD but shows normal channel video; don't infer version from pixels.
  No CPU pipeline/PC server changes this continuation. No public commit/release.

## 21 Nov 2026 16:12 - Clean MiSTer reboot gives Guide again; X picture retention + diagnostics

- Fourth W run AFTER A CLEAN MiSTer reboot successfully produced the native Guide
  again, identical first menu, no CPU/model halt. Evidence V079W-160547/guide.png,
  ram.bin and UART saved locally and on SD. Flash check all0 differences. Third
  HOT reload V079W-155114 failed before DMA7 (image state4, DMA7 descriptor still0).
  First/third executable text bytes9F4..FBE0C BOTH match the original extracted
  code exactly (zero differences). This points to decoder/reset/initial-source
  state across hot reloads, not code corruption. Exact cause still unproved.
- Before reboot backed helper scripts up to SD linux/pace/re-evidence/helpers/;
  restored them to /tmp afterwards. Relay auto-started and ring recreated; no PC
  server changes. Normal EEPROM remains intact. W still restored V078 after tests.
- Both real-decoder restart CONTROL tests PASS on OLD RTL: reset during DDR read,
  normal6-cycle and extended1024-cycle latency, each decodes a fresh header/picture
  after reset (61ms sim). These tests do NOT reproduce hardware's hot-reload failure.
  No memory shim/reset-controller changes made. Do not call them before/after fixes.
- Separate missing-background bug PROVED by failing regression: stopping ES input
  after a decoded picture discarded the frame (live0/valid0). Added explicit
  keep_picture to preserve the decoder/display after a native DMA7 snapshot.
  New test sim/tb_mpeg_keep_picture.sv FAILS before (old wrapper fixture accepts
  but ignores new input), PASSES after: held image survives stop+FIFO flush, then
  releasing it and resetting decodes a fresh image. Logs /tmp/mpeg_keep_{before,after}.log.
- Main Transport latches guide_picture_held only on real DMA7 completion in ES mode.
  It survives closing ES; release on new memory-picture input, real non-null TV
  video route, or reset. Source handover back to live gets the normal flush. The
  renderer uses the actual retained decoder picture under the OSD background mask;
  no host-injected bitmap is enabled for cold boot. CPU/core pipeline unchanged.
- X also adds read-only MV=xxxxxxxx telemetry for the decoder memory interface:
  bits31..24={DDR_busy,DDR_read,DDR_write,command_read,command_valid,response_write,
  response_almost_full,decoder_sync_reset_n}; bit23=enable2,22=busy,21..20=0,
  bits19..16=mem_shim state,15..8=accepted_write_count low8,7..0=read_count low8.
  Two-stage sample into clk_sys, diagnostic only. This should distinguish a
  blocked HPS port, a stranded shim command, and a decoder held in reset.
- Combined FP+MV UART regression PASS; full emu top lint PASS. New native capture
  integration test also latches keep_picture from actual DMA7 done, verifies all
  planes then stops ES and checks the picture persists: PASS at199ms simulated,
  /tmp/capture_hold_integration.log (input generated from flash only).
- Isolated X snapshot %TEMP%/Pace2500N_cold_picturehold_20261121, label0.7.9X
  (native still), fitter seed6. Compile exec82147, parent quartus_sh91068, map89240
  at last check. No concurrent fitter. Timing-gated X deployment watcher prepared
  as test-x-after-build.ps1, waits91068 and saves160s SD-backed hardware evidence.
  No public commit/push/release; still validate repeated cold boots/navigation.


- Further continuation: native capture routine80023748 decompiled read-only again
  in /tmp/cold_native_capture_lifecycle.txt, confirming the plane loop. New
  tools/decode_video_state.py decodes X MV snapshots and sampled-state counts.
  Stronger FIRST_BEAT restart control holds an old8-beat read at5999 cycles
  remaining, resets decoder, returns to normal6-cycle latency for NEW requests.
  PASS62ms /32s wall, /tmp/mpeg_epoch.log. Still does not reproduce hardware
  stall; no shim/reset RTL change justified. Initial all-reads-long variant was
  stopped before completion to isolate latency to the OLD accepted request.
  MiSTer process command line confirms restoredV078 (screenshot omits HPS OSD);
  current channel video is playing. X compile82147/watch72079 still running.

## 21 Nov 2026 15:45 - FIRST NATIVE GUIDE MENU FROM FLASH; repeat decoder failure remains

- Seed6 W finished15:22:44, ALL48 non-HDMI timing checks pass, minimum+0.171ns,
  CPU setup+0.689ns. Compressed/deployed as V079W, SHA256
  7e52f5538b2a7a3abaf1162cf341c6b552f356d461ee11a34b70337fadcb0f29.
  Test watcher exec82530 completed successfully. No public release/push.
- Genuine menu appeared on MiSTer from ORIGINAL FLASH with NO RAM/STATE download.
  MGL has only EEPROM(S1), FLASH_U202(F0), live TS(S0). Evidence in ignored
  re/deployment/coldboot_20261121/V079W-152249/: guide.png, full ram.bin, UART,
  flash/core/RAM hashes. Flash all262144 qwords match. CPU IR00/HALT00 through160s.
  Image resource state is no longer8; DMA7 descriptor ends on a completed chroma
  request (00667F78..00681477). No retained106/110 assertion found in that RAM.
  Shown Guide screenshot to user. This is a real milestone, NOT a reliable final build.
- FIRST menu has plain cyan backdrop and lacks the Sky Guide corner logo. WD ends
  05050101: decoder saw real headers/ends/pictures, but es_dma and dec_live are now0.
  Suspect coupling of decoder stop/soft-flush to display, which discards the last
  decoded still after native image capture. Need model proper picture retention;
  do not re-enable host-injected backdrop for cold boot.
- SECOND cold load/navigation test W-nav-153617 did NOT produce a Guide: screenshots
  guide/channels/info are blank/striped, while CPU/controller remain healthy.
  WD mostly000000D0, RD00000400 (ES memory mode active, input-ready0, decoder busy1,
  NO sequence-header/end/picture events). Thus a decoder startup/reset/handover
  failure, not evidence of a new CPU halt. Second test restored V078 at exit.
  Its105s UART/screenshots saved locally under W-nav-153617 and on SD.
- Investigating reset wiring BEFORE changes: mpeg2video soft_flush resets decoder
  request/tag FIFOs and all three decoder domains, but wrapper's mem_shim_burst
  currently receives only reset_n (POR), not the decoder memory-domain reset.
  Stale/aborted memory transactions may survive handover. DO NOT simply reset
  the shim while it presents a stalled Avalon command; preserve bus protocol.
  Also do NOT assume the one-time raster walk is wrong: the register file's
  modeline registers explicitly survive soft reset (hard_rst vs rst distinction).
- Added sim/tb_mpeg_restart.sv and controllable source/enable/flush regs in the
  existing MPEG bench (defaults unchanged). First A/B reproduction runs reset
  during an accepted DDR read, then attempts the original padded still from scratch.
  Exec id from latest tool, /tmp/mpeg_restart_{build,before}.log, binary
  /tmp/vl_mpeg_restart/Vtb_mpeg_restart. No decoder/reset RTL changed yet.
- Real-decoder input now reproducible directly from flash with prepare_capture_still.py;
  decoded byte equality with old padded test confirmed. Copy engine hardware passed
  the first native image callback/root-menu path. Keep one agent and one fitter only.

## 21 Nov 2026 15:08 - Success path attaches Guide root; regression needs flash only

- Read-only Ghidra /tmp/cold_backdrop_success_native.txt resolves the first native
  after the status/request-id assertions (o-code9FC72E7B): module1/E3 ->80085128,
  named set_window_root. DATA cells+2E114/+2E118 contain root80430A0C and window1
  in saved P RAM. This is a concrete link from a successful image completion to
  root-window attachment; do not patch the assertions or root-ready flag.
- Existing P UART INDEPENDENTLY confirms the requested profile, not just inferred
  disassembly: at145.16s W B00090B0=00108B78,20DC=000002D0,20E0=00000240,
  20D8=00008001. Its preserved descriptor matches the tested first Y-field fixture.
- Added tools/inspect_cold_boot_ram.py, which rejects partial dumps and reports the
  DMA7 descriptor, image-resource entries and POSSIBLE RETAINED assert arguments.
  On P it reproduces destination005E9678/end0061C077, state8 and source106/line110.
  Raw external RAM can lag dirty CPU caches, so these are not blanket corruption
  checks or proof that a retained assertion is currently executing.
- Added tools/prepare_capture_still.py and sim/test_video_capture_path.sh. The
  regression now reproduces its input using ONLY original2MiB FLASH_U202.bin:
  native720x576 image at flash0B4F48,16524 bytes, plus six524-byte drain blocks
  using the original000001B7 literal at223FC. Generated19668 bytes compare exactly
  to the already-passing decoder input. Shell syntax check PASS; original firmware
  cannot be overwritten by accidentally choosing it as output. No derived image
  or proprietary ROM bytes were added to tracked files.
- Ghidra /tmp/cold_capture_chroma_order.txt also confirms the native fill routine
  stores interleaved colour bytes into its chroma buffer, but does not by itself
  settle Cb/Cr versus Cr/Cb semantic naming. Preserve this uncertainty until native
  rendered output validates it. No speculative pixel-order change made.
- Checked the four-plane descriptor lifecycle: 80005962..76 sets a2=0x28 and
  calls literal80005C14=80000D34 to zero the descriptor at80108A60+channel*40
  before EACH setup. This is MIPS32 memset, verified with LinearM16 ISA_MODE=0
  (/tmp/cold_dma_descriptor_clear32.txt). The generic MIPS16 decompile of that
  helper is wrong-mode and must be discarded. No descriptor writeback/auto-clear
  needs to be invented in DMA7 to make subsequent planes work.
- Seed6 W fitter79300 (parent83344) continues; watcher exec82530 is waiting to
  timing-gate deployment and the160s SD-backed test. No second fitter or agents.

## 21 Nov 2026 14:54 - W has CPU tag-RAM hold miss; seed6 reroute running

- V full compile finished11:40, W finished12:20. BOTH fail one non-HDMI hold
  corner, so neither was exported/deployed: V CPU hold about-0.08ns, W-0.027ns
  (W setup CPU+0.428). V automatic watcher correctly stopped at its timing gate.
  All other non-HDMI checks positive. W is89% ALMs,444/553 RAM blocks,103/112 DSPs.
- Read-only post-fit STA pinpoints W's hold path: CPU instruction-cache
  tag_address_a[1] -> itagram2 MLAB registered address, Slow1100mV100C corner,
  -0.027ns, clock skew0.401ns. Same path FAST-40C is+0.011ns. Fitter already has
  All Paths hold repair and multi-corner optimisation enabled. No false paths,
  uncertainty changes, CPU pipeline edits or relaxed constraints added.
- Started SAME W RTL with fitter seed6 in isolated directory:
  %TEMP%/Pace2500N_cold_capture_seed6_20261121, parent quartus_sh83344,
  fitter79300, unified exec26647. Copied completed W synthesis database; only QSF
  SEED5->6 differs. Fitter active. This preserves CPU/serial behaviour and aims to
  fix the tiny placement/routing hold miss; it does not prove hardware boot yet.
- Timing-gated watcher test-w6-after-build.ps1 waits83344, requires all48
  non-HDMI checks positive, converts/uploads W compressed RBF, verifies hash,
  runs SD-backed cold-test.sh160s and downloads evidence. No other hardware test
  active; MiSTer remains on V078. Original V/W reports and sources preserved.
- Full slow V simulation COMPLETED34s /588887678 instructions,27878 interrupts,
  CPU errors00, model halt00, no unmapped accesses. Warm reset and application
  startup succeeded. Later VM exit6 repeats, expected in this bench with no MPEG
  header parser or DMA7. Do not mistake this older bench for the new capture path.
  Saved re/deployment/coldboot_20261121/cold_deviceclock_run.log (ignored).
- Strengthened REAL-decoder capture test: metadata must equal the decoder's actual
  display-bank register throughout each copy, and copied Y must have substantial
  variation, preventing a false pass on empty/wrong-bank zeros. PASS all622080 bytes,
  Y range0..255, finish179ms /83.5s wall. New flags guard restricts descriptor high
  control bits to001C0000, verified directly in original literal80005C68; wrong
  direction flags are rejected D7. Unit packed/strided/stop/invalid cases PASS.
- sim/build_mpeg.sh now exits on compiler failure so it cannot run an old binary
  after a failed rebuild. Added tools/decode_fp_state.py for W's FP state snapshots.
  Example --word71234567 decodes correctly. UART and DMA7 IRQ regressions PASS.
- Ghidra /tmp/cold_controller_event_masks.txt confirms the serial worker receives
  TX-queue events only when its mask includes bit2; helper0689C enables that bit
  while idle,068C0 removes it after loading an outgoing message. No speculative
  FIFO/handshake changes on this observation; wait for physical W FP snapshots.

## 21 Nov 2026 11:10 - Controller snapshots; SD evidence storage; firmware drain padding confirmed

- U second hardware run (U2) reached loader command44, then stalled without CPU/model
  errors. Unlike the malformed T capture, its status52 reply is EXACTLY03 03 52 02 00
  with no duplicate status byte. No later controller traffic after command44's last
  transmit byte. Saved U2-uart.txt; this does not prove the application/I2C fix yet.
- Ghidra read-only /tmp/cold_controller_driver_task.txt decompiles loader9FC05424:
  it keeps clock GPIO high when transmit/receive are both idle and waits for a
  controller byte; otherwise it lowers the clock and waits for transfer IRQ. ISR
  9FC053E8 reads RX into its one-byte software mailbox, clears ready, then activates
  deferred handling. No new handshake behaviour changed on this evidence alone.
- W now includes low-bandwidth FP=xxxxxxxx telemetry, a read-only clk_sys snapshot:
  bits31..24={clock_waiting,tx_full,tx_valid,wire_active,ack_pending,wire_escape,
  tx_escape,RX_ready}, bits23..16=serial_rx,15..12=wire_pos,11..8=wire_len,
  7..3=tx_count,2=GPIO0,1=CSI enable(bit7),0=EMMA serial IRQ mask(bit13).
  This avoids guessing a stalled FSM from dropped UART event lines. EXTRA_FP defaults
  off for older users; the main Transport top enables it. Both UART variants PASS
  starvation/framing regression (six PACE snapshots with continuous PROF output).
- Re-linted the connected emu top after telemetry changes: PASS. DMA7 IRQ regression
  PASS. Optimised expected-span arithmetic to constants (no 32-bit multiplication).
  Pixel-copy test also now stops an in-flight PIXEL read, ensuring no write or done.
  All six packed/strided plane cases still PASS. W snapshot updated while V parent
  76088 is still running; no source mutation during compilation. W exec98138 waits V.
- The repeated RAM dumps filled MiSTer's246MiB /tmp filesystem during U2. U2 RAM is
  PARTIAL13537280 bytes; do not treat it as a valid16MiB capture. The test exit trap
  restored V078. Moved this session's cold079* RAM/UART/test-log artifacts to SD at
  /media/fat/linux/pace/re-evidence/coldboot_20261121, verified SHA256 before unlinking
  each temporary original. Manifest there; /tmp now29MiB used,218MiB free. Did not
  remove the live stream ring, relay log, normal EEPROM or user data.
- Future lab script re/deployment/coldboot_20261121/cold-test.sh writes evidence to
  SD, validates full dump length and hashes, and restores V078 on exit. Uploaded to
  /media/fat/linux/pace/cold-test.sh. V/W MGLs still contain only EEPROM/flash/live TS.
- Existing padded decoder input is consistent with original firmware code, not a
  ROM edit: 8000FA04 sends524-byte drain blocks through8000F890 and writes B7 at+20B;
  its literal at9FC223FC is000001B7. The raw MPEG file alone does not include those
  driver-generated trailing blocks. Integration bench still uses six padded blocks
  after the original16524 bytes; exact hardware traffic should remain the authority.
- Timing-gated V deployment/test watcher prepared (test-v-after-build.ps1): waits
  V compile, requires all48 non-HDMI checks pass, converts/compresses, verifies upload
  hash, tests160s and fetches evidence. W waits V separately and will fit concurrently
  with this hardware test (one fitter only). No public release/push.

## 21 Nov 2026 10:57 - DMA7 implemented and tested; W queued, V fitting

- Added rtl/pace_video_capture_dma.sv, connected to the real decoder's completed
  display-bank metadata and the guest DDR arbiter (new owner8; owner tags now 4 bits).
  B00090B0 selects the descriptor, B0009010 bit7 starts/stops, completion sets
  B0009120 bit7 and the shared DMA IRQ; B0009130 acknowledges it. These addresses
  and descriptor layout were rechecked in Ghidra /tmp/cold_dma7_setup_confirm.txt.
- Corrected the earlier design note: decoder storage is RASTER, not tiled.
  mem_addr.v stages7-9 use Y stride2*mb_width, chroma stride mb_width. Four banks
  each occupy 0x18000 qwords: Y+0, Cr+10000, Cb+14000 at HPS38000000. Pixels are
  MSB-first, whereas guest DDR byte lanes increase from lane0, so the copy reverses
  Y bytes and interleaves Cb/Cr. Cb/Cr order still needs confirmation against the
  original firmware's rendered output; no claim of a complete Guide yet.
- Supported profile: uncropped PAL720x576, controls8001/8801/8401/8C01, 720-byte
  destination rows. Supports packed planes and chroma rows with a 720-byte gap
  (driver modes4/5 subsequently duplicate alternate rows in software). Other
  geometry/control/descriptor shapes report D7 without fake completion. Real
  pixel writes must all be accepted before done. The decoder pauses new display
  pickups during capture, after acquiring its first valid bank; the DMA waits two
  field boundaries. mem_shim_burst is write-through, not a dirty writeback cache.
- Tests PASS: sim/tb_video_capture_dma.sv verifies every byte in both Y fields and
  both interleaved chroma fields, plus strided chroma, bank2, delayed reads,
  backpressure, hold during read response, stop/restart and invalid geometry.
  Found/fixed a 9-bit source-row wrap (PAL needs10 bits) and lost read response
  during hold while writing this new module. Test pattern distinguishes those rows.
- sim/tb_video_capture_irq.sv PASS: descriptor, no early IRQ, true completion IRQ,
  stop without completion, other-DMA coexistence and simultaneous stale START RMW.
  Existing front-panel and I2C regressions still PASS. Full emu top-level lint PASS.
- sim/tb_video_capture_path.sv PASS with the REAL MPEG decoder: all622080 copied
  bytes match its decoded DDR pixels; stable display bank, four actual completions,
  finish179ms simulated /94s wall time. Uses existing /tmp/guide_still_fw.hex:
  original16524-byte still plus drain padding/end codes (19668 bytes total). The
  unpadded single still does not drain this decoder; that run had zero pickups.
  Do not describe this bench as proof of the raw hardware feed or a Guide boot.
  Logs /tmp/capture_mpeg_{build,run}.log; top lint /tmp/capture_top_lint.log.
- U full build finished10:40; all48 non-HDMI timing checks positive (min hold+0.150,
  CPU setup+1.171; only HDMI negative). Exported/deployed compressed V079U under a
  separate filename. First160s hardware test stalled in the loader's controller
  exchange after two transmit bytes; IR/errors00, HALT00. Thus no proof yet of its
  I2C fix on hardware. U UART/RAM/diagnostic screenshot in ignored coldboot_20261121.
  Flash qword check all0 differences. Test restored V078. Normal EEPROM untouched.
- V fitter PID79992 / parent76088 running; includes device_tick clock-domain fix
  missing from U, plus status52 trace. Full slow V sim exec86771 passed warm reset
  and entered application at11.034s with zero CPU errors; still running (~14s now).
- W isolated snapshot %TEMP%/Pace2500N_cold_capture_20261121 queued behind V's
  parent76088, so one fitter only. Adds the tested DMA7 path and first-command
  GPIO/ready trace window (U stalled before its narrower status52 trace window).
  New core error D7 also freezes CPU trace. Main OSD label remains0.7.9; isolated W
  is labelled0.7.9W (picture capture). No ROM/RAM writes, CPU pipeline changes,
  snapshot injections, public push or release performed in this continuation.

## 21 Nov 2026 10:29 - Backdrop snapshot uses unimplemented DMA7 (next UI blocker)

- Followed the source-id106/line110 assertion further. Actual event sender 80057A4C
  constructs {u16 class=0040, u16 status=param3, u32 command=param4, u32 handle=param2};
  the P event's status1 is therefore an A/V completion status, not a window id.
- P's still-image resource table at 80161FCC has entry1 {00000000, FFFFFFFF, 00000008}.
  80058F14's command23 arm sets this state8 on invalid image rectangle or failure of
  the video driver's image-fetch method (+164), then posts a failure completion.
  The actual dimensions at 80106390/92 are 720/576, so the old P capture is NOT simply
  missing decoded width/height. Its request rectangle retained in 80101620 is 0,0,720,576.
- Driver vtable at 800FC520: +E0=80021079 (width), +E4=80021081 (height),
  +130=80021C59 (rectangle adjust), +164=80023749 (copy decoded image into RAM).
  80023748 iterates field/colour planes and calls 8000A4AC. That function sets up a
  real DMA channel SEVEN transfer via 80005900(7,0,destination,span), writes the video
  copy control at B00020D8 and geometry B00020DC/E0, waits on semaphore801062F8 for
  11 ticks, stops channel7, and checks its completion/error through 80005DFC.
  This core currently implements DMA5 and DMA12, NOT DMA7, so a real image copy cannot
  complete. This is a concrete missing hardware path to implement, not permission
  to acknowledge without copying pixels or to bypass the UI assertion.
- Important correction: B0006040 is only an additional busy poll in 80023748. The
  actual copy datapath registers are B00020C0 / 20D8 / 20DC / 20E0, already in the A/V
  UART trace. Added B0006xxx WRITES to the queued V trace too (no busy-read flooding).
- Ghidra /tmp/cold_backdrop_image_driver.txt and /tmp/cold_video_copy_engine.txt contain
  the original width/height, rectangle adjust and copy setup code; existing
  re/av_f4_decompile.txt covers 80058F14's completion/status logic. New report
  /tmp/cold_backdrop_completion_event.txt proves the event layout. All are read-only.
- Design investigation only; DMA7 is not implemented yet. The MPEG decoder owns its
  framebuffer separately at HPS 38000000 (mem_shim_burst), while native DMA7 writes
  firmware-allocated planar image buffers in guest RAM. A correct implementation must
  transfer actual decoded picture data and then signal completion. Options being read:
  decoder's exposed-but-unconnected Y/U/V raster pins, or direct framebuffer reads using
  the documented tiled layout in rtl/mpeg2/mem_codes.v and mem_addr.v. Reading the
  displayed frame requires a stable frame-bank selection and write-cache coherency;
  do not assume a hardcoded frame id or write dummy pixels. No datapath has been edited.
- V waits behind U (exec65338); its isolated Transport source now includes B0006xxx write
  tracing, matching main plus version label. U fitter still optimising, no second fitter.

## 21 Nov 2026 10:17 - Older P Guide failure resolves to original UI assertion

- Read-only RE while builds run: OpenTV native (0,43) at 8007DF94 is a printf wrapper,
  confirmed by its formatter 8007D840. The call immediately before status-6 exit is
  the EPG's assert helper at bytecode 9FC4A420..438. DATA+E49C contains
  "Assert : F:%s, L:%d.". Native (0,11) then requests VM exit 6; it is not an unexplained
  CPU exception. This does not establish that the current pre-Guide T halt is that exit.
- Independent HARDWARE P saved RAM (not merely a simulation) retains the assert args:
  EPG DATA copy starts 0045CB5C (RSRC, count 764), format 8046AFF8, source-id pointer
  804753C0 -> "106", line 0x6E (=110), saved bytecode return 9FC72E55. These values are
  in the VM stack at 00494D30..60. The root object 80430A0C already has +14 = 1.
  Do not revive the old root-ready RAM patch; the native cold path already sets it.
- Bytecode at 9FC72E3E loads an unsigned short from event+2 and asserts at source-id
  106 line 110 if nonzero. The actual saved event at 00494DC0 is:
  00400001 00000023 00000001 80494E1C. Thus event+2 status is 1, event id 23, request id 1.
  The next assertion (line111) compares root+14 request id against event+8; both are 1.
  Operand decoding is checked against actual interpreter helpers 80068D98 / 80068DA4
  and handler 8006C116: high nibble 1 -> short offset2, low nibble C -> FP[-16].
- Native (3,3C) = 8005B6E4 constructs A/V command 23 (the memory-fed backdrop request),
  handled at 8005803C. So the older blank-Guide capture contains a nonzero backdrop
  completion status. This narrows the UI issue; it does NOT yet identify whether the
  A/V allocator, memory feed, decoder flush/sequence-end, DMA8, or another stage failed.
  Do not fake completion or change the assertion/default-return literal. Once startup
  is reliable, correlate UART WD raw/gated end/sequence counts and the actual driver
  return path. The bench lacks decoder header events and can fail differently.
- Read-only Ghidra reports in /tmp/cold_ocode_{main_exit,callback,member_loads}.txt,
  /tmp/cold_member_nibbles.txt, /tmp/cold_backdrop_native.txt, /tmp/cold_backdrop_gate.txt.
  Existing re/epg_still_provider_v071.txt and re/av_manager_decompile.txt cover command23.
  Tentative static bytecode listings are private re/deployment/coldboot_20261121/
  ocode_assert_{candidates,context}.txt. The exact assert site is independently confirmed
  by saved args and bytecode call/return addresses, not just a speculative linear sweep.
- U fitter PID74612 (parent64236) continues; V waits in exec65338. Full V simulation
  exec86771 is running (~2 simulated seconds at 10:16), do not restart needlessly.
  MiSTer has been restored to stable V078 after the T blank-EEPROM control.

## 21 Nov 2026 10:07 - Remove unsynchronised CPU counter from peripheral timing

- RAM from T2 contains the malformed Guide key body 05 00 02 02 00 0C C0 at 002AB0B1.
  Thus duplicated data reaches the firmware's receive buffer, not just a UART text
  reconstruction. Handshake/ready tracing in U will distinguish the remaining cause.
- The blank-EEPROM T control also reached the application and the SAME E7 I2C halt;
  normal save contents are not the cause of that failure. It completed and restored
  V078. Evidence T-blank-{uart.txt,ram.bin} saved under ignored re/deployment/coldboot_20261121.
- Found a genuine functional clock-domain crossing: pace_guide_peripherals used
  retired!=last_retired to advance CSI, I2C and serial0 delays. retired comes directly
  from clk2x, while these devices run on clk_sys; Pace2500N.sdc declares those groups
  asynchronous. These are functional transfer completions, not display-only counters.
  Timing passes therefore did not validate this crossing, and the old design cannot
  complete a transfer at all when the CPU stops retiring instructions.
- NEW main-source change AFTER isolated U: device_tick = WALL_TIMER ? 1 : tick.
  All serial/I2C completion delays and the completion-cycle GPIO guard use device_tick.
  Default WALL_TIMER=1 now runs these delays in clk_sys time, independently of CPU;
  the legacy instruction-timed profile remains explicit WALL_TIMER=0. The CPU, CP0 Count,
  EMMA timer and byte-receipt gate are unchanged. In hardware the unused retired compare
  should optimise out of functional device control. This removes the unsafe crossing;
  it is not yet proof that it explains the captured duplicate bytes.
- New PAUSE_RETIRE variant of sim/tb_front_panel_receipt.sv FAILS before with "Controller
  did not deliver a byte"; PASSES after, including late/completion-cycle GPIO tests and
  all status/identity/heartbeat checks. STALL_RETIRE variant also passes. The I2C abort
  regression now freezes retirement during its normal EEPROM read; it passes with data
  A5 and the correct pointer advance. Unsupported A3 still reports E7.
- V source snapshot prepared at %TEMP%/Pace2500N_cold_deviceclock_20261121, version
  0.7.9V (device clocks). Exec 65338 waits for current U quartus_sh PID 64236 to end,
  then compiles V; ONLY ONE fitter at any time. V has all U fixes and handshake tracing,
  plus the clock-based transfer timing. U still uses the old instruction counter.
- Full V slow-memory simulation building/running, exec 86771, binary
  /tmp/vl_cold_deviceclock/Vtb_sys, work /tmp/vl_cold_deviceclock_work, logs
  /tmp/cold_deviceclock_{build,run}.log. +cold +lat=20 +busy=30 +cycles=1700000000
  +status=50000000 +vmtrace +fptrace +printf +natives +exctrace +ts=/tmp/home_tp40.ts.
  tb_sys fptrace now observes devices.device_tick, matching the real completion event.
- U normal test launcher Pace2500N_V079U_Live.mgl and ignored remote test source
  re/deployment/coldboot_20261121/cold079u-test.sh are prepared locally, not yet deployed.
  First Guide is at 65 s, UART capture 160 s, automatic V078 restore. Check non-HDMI timing
  and export U when it finishes; use the targeted trace if startup still fails.

## 21 Nov 2026 09:55 - U restarted with targeted controller handshake trace

- Second T run did NOT reach warm reset: loader idles at 9FC0DE4C/64, HALT=0. UART
  reconstructs status reply 03 03 52 02 02 (five bytes, duplicated 02), followed by the
  terminator; the later Guide key frame also has a duplicated opcode 02. Ghidra loader
  receive validator 9FC05738 requires total length == frame[0]+1, so the first frame
  is rejected before its callback. This is an observed malformed RECEIVE sequence;
  it does not yet prove which clock/IRQ/CPU-read path duplicated it. Do not guess a FIFO
  or patch the firmware to accept it. Both loader and application ISR read 9010 once
  after checking 9020, then clear ready before waking the serial task.
- Added UART trace of 9020 and A000 only when serial_frames is 2/3 (loader status)
  or 8/9 (application status). All data-register tracing remains. The narrow window
  avoids flooding the UART during all other commands and captures the next failed
  handshake. This is observation only, no guest response changes.
- Also explicitly reset i2c_receive in the peripheral reset branch, alongside its
  already-tested START/STOP cancellation. U was stopped early in its first fitter
  (verified PID 72100 child of quartus_sh 65724) and restarted 09:51:40, exec 26043.
  Same directory %TEMP%/Pace2500N_cold_i2cfix_20261121; first attempt log retained as
  compile-before-trace-restart.log. It includes all three I2C cancellations and the
  targeted handshake trace. No other fitter runs.
- The failed T2 run is complete, V078 restored, ignored T2-{uart.txt,ram.bin,tasks.json}
  evidence saved. Loader task magic exists but dirty HPS-visible neighbour links prevent
  census validation (task_count 0). That is not evidence of RAM corruption.
- A separate-erased-EEPROM T control is running, exec 61846 (started about 09:53),
  /tmp/cold079tblank-test.sh, 200 s UART and first Guide at 90 s. Launcher
  Pace2500N_V079T_BlankEE.mgl uses /tmp/pace_blank_eeprom.bin, leaving the normal EEPROM
  file unchanged. It restores V078 automatically. Still the T bitstream with known I2C
  abort defect: this control tests startup variation and factory-default initialization.
- Original ROM path is firmware/FLASH_U202.bin (not original_firmware). Ghidra read-only
  reports /tmp/cold_loader_serial_driver.txt and /tmp/cold_loader_link_task.txt include
  the loader's actual serial ISR, receipt path, frame-length validator and dispatcher.

## 21 Nov 2026 09:44 - T boots past warm reset; next I2C abort defect reproduced

- S finished 06:28:29, but CPU setup is -0.029 ns. It was NOT exported or deployed.
  T finished 07:11:11: all 48 non-HDMI checks pass, minimum +0.247 ns, CPU setup +1.005 ns.
  RBF output_files/Pace2500N_V079T.rbf SHA256
  0f6ae34bf6ba76854a384bf5a0fdbbd28fae8a9ecf18d450661c296ec516cd88.
- Full T slow-memory simulation completed 34 simulated seconds / 590,795,057 retired,
  no CPU errors. The original 7.539 s MCU reset now succeeds, application entry at
  11.043 s. This directly fixes the identical old slow-run warm-reset failures.
  Its first AV_SELECTION returns FFFFFFFF at 31.201791 s; no VM exit by the 34 s limit.
  The +watchval=FFFFFFF0 capture early in the loader is a normal literal write at
  BFC18E4C, NOT a bad SP. Do not mistake that generic value watch for the SP trigger.
- The normal S simulation completed 34 s with repeated VM exit 6. The first caller
  is 8006E34F -> 8006E318, native (0,11), not the debug subsystem's other status-6 path.
  This remains bench evidence; the bench lacks sequence/GOP/picture parser events.
- Whole-CPU IRQ/reset regression fails BEFORE the fix with first post-reset WB at
  BFC00380; AFTER passes three resets each at latencies 1/6/20/60/300. A later +tlb
  fetch-miss variant passes both before and after: it is a passing control, not a
  separate reproduction of this defect. GHDL lowers exceptionStage1 to exceptionstage1
  in the generated Verilog, which the testbench now uses correctly.
- T was deployed at 09:38 using ONLY original flash + normal EEPROM + live TS, no
  RAM/STATE files, extra ROM reload, forced application PC, or guest-memory edits.
  Physical warm reset reaches the application, whose [9F4:FBE0C] executable bytes again
  match the independent extraction exactly (1,029,144 bytes, zero differences).
  HOWEVER it does NOT reach the Guide: before-key and Guide screenshots are clear blue.
- T then hits model HALT E7 near 60.5 s, followed by the expected CPU stall flag 02
  because io_ready is suppressed by the model halt. E7 means an I2C receive on an
  unsupported address, NOT demodulator APR overflow (that would be E5). The frozen
  trace is complete (227 pages), last transactions START 9A then EEPROM address A0.
  Thus it froze on this model halt, NOT on the VM-exit-PC trigger. No hardware VM exit
  is proved by this capture. RAM census validates 20 tasks at the pre-halt capture.
- Concrete model defect reproduced in sim/tb_i2c_abort.sv: request A1 receive, STOP,
  START, address A0 -> E7. STOP cancelled i2c_delay but retained i2c_receive, and the next
  transmit's completion reused the old receive flag against its new address. START
  had the same omission. Both now cancel pending receive and delay. The regression
  FAILS before the fix and PASSES after, including normal read via the EEPROM's load
  port, pointer advance, repeated START cancellation, and continued E7 for unsupported
  A3 reads. Ghidra /tmp/cold_i2c_flow.txt shows the real driver STOP at 80006F2E/30 and
  next transaction START at 80006AFA/FC. No unsupported reply zeros were added.
- U compiling since 09:43:41, exec 22462, isolated snapshot
  %TEMP%/Pace2500N_cold_i2cfix_20261121, version 0.7.9U (I2C abort). It is T plus the
  above abort fix. Verify all non-HDMI timing, export, deploy normal cold MGL and test.
- A SECOND normal T run is currently in progress (09:43:52, exec 19125), remote
  /tmp/cold079t2-test.sh, 160 s UART capture /tmp/cold079t2-uart.txt, first Guide key at
  75 s, then RAM/diagnostics. It restores V078 automatically. Use it to check variation
  and potentially capture the next startup stage while U fits; T still has the I2C bug.
- First T evidence is private/ignored re/deployment/coldboot_20261121/T-{ram.bin,uart.txt,
  frozen-trace.txt,tasks.json}. Full remote capture can be recopied after completion.
  No public push/release. No original firmware changed. User still wants real cold boot.

## 21 Nov 2026 06:18 - Pending CP0 exception survives warm reset (reproduced)

- Both slow-memory runs fail IDENTICALLY at the first MCU reset, before and after the
  bridge fix: reset at 7.539 s, EPC retains pre-reset 9FC11161, then the first exception
  handler runs with cleared hardware SP and writes FFFFFFF0, causing recursive TLB-store
  exceptions at 9FC0EE50. This narrows the problem beyond the independent bridge defect.
- rtl/r4k/cpu_cop0.vhd reset branch did not clear exception or exceptionStage1 outputs.
  A pending interrupt redirect could therefore survive reset and bypass the reset ROM.
  Added those TWO reset assignments (plus explanatory comments), no instruction changes.
- sim/tb_cop0_warm_reset.vhd reproduces pending IRQ + reset while stalled: FAIL before,
  PASS after. sim/test_cop0_warm_reset.sh runs it from clean GHDL libraries, no firmware.
- Stronger whole-CPU synthetic-ROM regression sim/vl/tb_warm_reset.sv runs the actual CPU
  with wrapper and 20-cycle DDR responses. BEFORE fix it FAILS with first post-reset WB
  PC=BFC00380 instead of BFC00000, matching the real failure. After-fix run is compiling
  (/tmp/vl_reset_after): PASSES all three warm resets in order (87 us simulated).
  This test uses no RAM/STATE/firmware files or guest patches.
- T isolated build snapshot is %TEMP%/Pace2500N_cold_exceptionfix_20261121. It includes
  the pending-exception reset and exact-cycle controller collision fixes, plus all S
  changes. Exec 86233 waits for S's quartus_sh PID 67652 to finish, then compiles T.
  No two fitters run concurrently. S still lacks these last two fixes.
- Full T slow-memory simulation started after compilation at ~06:16, exec 36935,
  /tmp/cold_exception_run.log, binary /tmp/vl_cold_exception/Vtb_sys, work
  /tmp/vl_cold_exception_work, +cold +lat=20 +busy=30 +vmtrace +fptrace +printf +natives
  +exctrace +ts=/tmp/home_tp40.ts +watchval=fffffff0 +watchmax=1. Let it continue.
- Old slow-run logs saved under ignored re/deployment/coldboot_20261121; both old slow
  processes stopped after identical first-failure evidence. The after log additionally
  contains a diagnostic SECOND board reset at 8.720784 s (GDB changed warm_count only,
  plus host trace options; no guest RAM/state edits). That reset took the reset-ROM path.
  It is NOT the untouched before/after comparison after that timestamp. Do not claim
  it proves successful ordinary cold boot. The normal S simulation remains unmodified
  and running in /tmp/cold_resetfix_run.log (about 18 s simulated, no CPU errors).

## 21 Nov 2026 06:08 - Live continuation and controller collision fix (in progress)

- R completed with CPU setup +1.306 ns and all 48 non-HDMI timing checks positive.
  HDMI is excluded per the user's instruction. Normal hardware R then failed at the
  loader warm reset: recursive 9FC0EE50/54 exception prolog, bad stack, HALT=0 and
  cpu_errors=0. Original flash comparison still passed. This is not a solved cold boot.
- A diagnostic R MGL repeats only the original FLASH download with delay=25 seconds
  (Main implements delay in seconds). That prolonged CPU hold preserves warm RAM and
  reaches the application, whose executable region again matches the independently
  extracted code, all 1,029,144 bytes. This reload is a diagnostic, not the desired boot.
  It later stalls after outgoing startup command 52 reaches TX escape byte 1B.
  HPS task census cannot validate cached/dirty task links; do not call that RAM corruption.
- S was restarted at 05:34:52 from %TEMP%/Pace2500N_cold_resetfix_20261121, exec 44188.
  It has bridge reset cancellation, query 21/23/28 payloads, 67.5/33.75 MHz clocks,
  pending UART telemetry, and a first-invalid-stack trace trigger at loader exception
  prolog PC 9FC0EE4C/BFC0EE4C. Trigger ignores valid SP upper bytes 80/A0. The focused
  trace test passes. Check core timing after fitting, then test normal S cold boot.
- Three simulations remain running, do not restart needlessly:
  /tmp/cold_resetfix_run.log (started 05:07, normal latency, exec 83627),
  /tmp/cold_slow_before_resetfix.log (05:37, exec 64628), and
  /tmp/cold_slow_after_resetfix.log (05:37, exec 92013).
  Slow pair uses +lat=20 +busy=30. Normal S has passed all initial controller replies,
  including command 52 and the full identity, by 15.288 simulated seconds. Thus the
  physical controller stall is timing-sensitive, not universal in this revision.
- Read-only GDB inspection of the running normal simulation works: portable gdb in
  /tmp/pace-gdb-root, LD_LIBRARY_PATH=/tmp/pace-gdb-root/usr/lib/x86_64-linux-gnu.
  /tmp/pace_debug_root.o provides DWARF for Vtb_sys___024root. Break at entry of
  Vtb_sys___024root___eval, root pointer in RDI, inspect, delete breakpoint and detach.
  Host attachment does not modify guest memory. /tmp/pace-cold-debug.gdb is on Windows
  TEMP (WSL /mnt/c/Users/joelw/AppData/Local/Temp). The idle state after startup is
  tx_full=1, wire_active=0, clock_waiting=0: a queued dummy waiting for a future reply,
  not by itself a stalled transfer. Do not run apt --fix-broken: unrelated existing
  apt dependencies are broken; the portable debugger works without changing them.
- NEW main-source-only fix AFTER S isolation: GPIO low coincident with tick and
  clock_delay=1 previously restarted a just-completed transfer. Added exact-cycle
  regression to sim/tb_front_panel_receipt.sv: FAILS before fix with duplicated receive
  transfer; PASSES after ignoring that coincident edge. Existing receipt, delayed edge,
  full identity, status, and heartbeat checks also pass. No guessed FIFO or CPU edits.
  S does NOT contain this last collision fix; build a later core if hardware needs it.
- Native blue backdrop and logo are not a complete Guide boot. P had 41 valid tasks
  but both OSD field buffers entirely clear DC. Its RAM contains the synthetic BBC1
  service descriptor. Full-system bench currently lacks sequence/GOP/picture parser
  events, so its OpenTV status-6 exit must not be assumed to explain physical hardware
  until the hardware trace confirms it. Telemetry WA has GPU/SI counts; the diagnostic
  screen's similarly positioned values are DDR/bus statistics, not GPU completion counts.
- Evidence is private/ignored in re/deployment/coldboot_20261121. Stable V078 restored
  after each hardware experiment. No RAM/STATE loading or forced application PC is used
  by normal cold MGLs; the original firmware hash is unchanged. No public push/release yet.

## 21 Nov 2026 - Cold boot continuation, VM exit isolated (in progress)

- V079P booted original U202 through reset into the application on hardware. Two Guide
  presses produced the native MPEG backdrop and Sky Guide corner logo, but no menu text.
  Evidence: %TEMP%/pace-cold-20261120/P-guide.png and P-uart.txt. Captured P-ram.bin has
  a validated circular created list of 41 tasks (P-tasks.json); TASK0 waits on EVENT00,
  FETask on FeCmd, and TASK30 was runnable. No model halt or reboot trace trigger occurred.
  Its OSD descriptor at 00583FE8 is valid 720x576 8bpp, with both field buffers entirely
  clear colour DC. This is a firmware drawing/startup blocker, not hidden menu text.
- The two full RTL simulations completed. /tmp/cold_continue_run.log: 40 s, 1,469,417,370
  retired, no CPU/model/GPU error. /tmp/cold_receipt_run.log: 32 s, 1,045,156,687 retired,
  no errors. Both include PAL field interrupts and original flash from reset. Both now
  show OpenTV repeatedly starting and exiting with status 6, then CLEANING_UP/relaunch.
  The first exits occur around 25.59 s. GPU completions are repeated clears (48 by 40 s).
  The receipt-only patch does not remove this repeatable application failure.
- Ghidra: 800516BC launches the module and at 800519A6 calls 8006E1E8, saving its return
  at 800519AE. The VM uses real setjmp 800F8D5C / longjmp 800F8D90 and context 8011FF50.
  8006E318 terminates the VM with its argument. 8006E344 calls it with 6 and is native
  (0,11), flash pair 9FC29C28. A second status-6 path exists at 800709D8 (debug subsystem).
  The registered fatal callback 8006E0FC exits with 5, so status 6 must not be called a
  CPU exception or identified with that callback without a trace. Reports /tmp/cold_vm*.txt.
- Controller replies are now structurally valid: 52 has its one-byte status (2, the
  software model's disclosed profile); 10 has six explicit unmodelled identity zeros;
  other acknowledgements echo their command instead of invoking the opcode-10 callback.
  sim/tb_front_panel_receipt.sv verifies byte consumption, delayed GPIO edge, 52 payload,
  the full escaped six-byte identity and heartbeat opcode. It passes with the patch.
- Fixed telemetry starvation in pace_debug_uart: a pending status frame survives a busy
  UART. sim/tb_debug_uart_pending.sv passes (6 PACE and 3 PROF), original HEAD fails
  with 0 PACE under continuous PROF. This is diagnostic-only, no CPU stall/change.
- V079P timing: CPU -0.011 ns; V079Q (receipt/protocol/UART fixes) CPU -0.411 ns. Q was
  compiled successfully but NOT deployed. TimeQuest's CPU path is decodeValue -> jump
  FetchAddrSelect -> instruction TLB mini_hit -> stall1. HDMI also fails as already known.
- V079R compiling since 04:39 from %TEMP%/Pace2500N_cold_vmexit_20261121. CPU is now
  67.5 MHz (VCO/20), memory side 33.75 MHz (VCO/40); COUNT_NUM=3/DEN=10 retains 20.25 MHz
  CP0 Count. No CPU pipeline edits. TRACE_PC=800519AA freezes just after VM return,
  before its status print; trace survives warm reset. UART also includes B0004xxx OSD.
  Wait for core timing to pass before treating hardware results as validated.
- Matching new RTL sim started 04:42: /tmp/vl_cold_vmexit/Vtb_sys +cold +cycles=1700000000
  +status=50000000 +vmtrace +printf +natives +ts=/tmp/home_tp40.ts
  +mlog=/tmp/cold_vmexit_mlog.txt > /tmp/cold_vmexit_run.log. Built via W=/tmp/vl_cold_vm_work
  OBJ=/tmp/vl_cold_vmexit COUNT_NUM=3 COUNT_DEN=10 bash sim/vl/build.sh. Do not restart it.
  +vmtrace logs AV_SELECTION, VM_EXIT, and the registered fatal callback, with a short
  instruction ring. It is read-only observation. Still no RAM/STATE loading or guest edits.
- That simulation was restarted at 04:50 after adding VM_NONLOCAL_EXIT instrumentation
  at 8006E318 as well as the fatal callback. It now records the terminating argument,
  caller, saved registers and preceding 200 instructions, avoiding an ambiguous status alone.
- Additional main-source fixes AFTER the isolated R build: responses 21/23/28 explicitly
  include frame[3]=0 (unknown-zero profile). Ghidra callbacks 80029DF0/8002A740/8002A5FC
  each consume that byte. R predates this change; the focused front-panel test includes 28.
- A second concrete defect is fixed in the main pace_r4k.sv bridge. reset_sys previously
  reset the state machines but retained request/ack toggles; an unfinished MMIO write was
  reissued when reset ended. hold_sys also resets the CPU and could replay completed writes.
  Reset/hold now cancel both handshake halves. sim/tb_r4k_reset_bus.sv (Icarus -g2012 -i,
  CPU interface driven directly) FAILS before the patch with "Warm reset replayed the old
  peripheral write" and PASSES after it, including pending DDR and fresh read/write checks.
  No CPU pipeline/instruction changes. The slow-DDR handoff crash is a possible consequence,
  not yet a proven one. R predates this bridge fix too.
- /tmp/vl_cold_resetfix is being compiled (05:05) with the bridge + complete query replies;
  W=/tmp/vl_cold_vm_work OBJ=/tmp/vl_cold_resetfix bash sim/vl/build.sh nosynth.
  Launch its full cold run when compilation completes. Keep the R comparison run running.
  Build the corresponding S hardware after R finishes, to avoid two memory-heavy fitters.
- tools/decode_frozen_trace.py decodes the latest complete frozen PROF ring, newest copied
  pages preferred. Verified on O-tasks-uart.txt: 227 pages, 1024 instructions, 64 bus entries,
  final write B2006000=A8. Firmware-derived output belongs in ignored re/deployment.
  All 20 Python tests pass, one optional FFmpeg skip. U202 SHA256 remains 32f6b2e8...f63d38c7f.
- Hardware P text comparison: P-ram.bin[000009F4:000FBE0C] is IDENTICAL to the independent
  extraction in re/application_initialized_segments.bin, all 1,029,144 bytes, zero mismatches.
  The firmware's own copy/decompression therefore produces the expected executable image.
- P repeated-input test (21 Nov 05:17) tried four Guide presses, Sky then Guide, and standby
  then Guide. Still only clear colour/backdrop/logo, no menu rows. Evidence in ignored
  re/deployment/coldboot_20261121/cold079p-retries-{uart.txt,ram.bin}; task census still 41.
- R simulation reaches the loader reset at 5.577 s and application entry at 8.030 s with
  corrected startup replies/67.5 MHz and zero CPU errors. The reset-fix comparison is running
  in /tmp/cold_resetfix_run.log (started 05:07), 34 s limit, same vmtrace/printf/natives,
  with +exctrace and +mlog=/tmp/cold_resetfix_mlog.txt. Neither run has completed yet.
- S hardware source %TEMP%/Pace2500N_cold_resetfix_20261121 is ready. A PowerShell job
  (exec session 70595) waits for R's full successful compile, then compiles S automatically.
  S also freezes the diagnostic trace on CPU error flags. No two fitters run concurrently.
- Remote /tmp/cold079r.sh is ready for the diagnostic test (200 s, automatic V078 restore).
  A SEPARATE erased EEPROM input /tmp/pace_blank_eeprom.bin (64 KiB FF) and local
  Pace2500N_V079R_BlankEE.mgl are prepared for a factory-startup comparison if needed.
  The normal EEPROM save file has not been replaced. The blank MGL still needs upload.

## 20 Nov 2026 - Codex cold boot continuation (earlier work)

- User wants the cold-boot fork completed with original firmware and persistent EEPROM,
  eliminating external RAM.bin/STATE.bin. Use one agent only. Current branch is cold-boot.
- Original U202 is unchanged. The fresh system run /tmp/cold_continue_run.log uses
  /tmp/vl_cold_continue/Vtb_sys +cold +cycles=2000000000 +status=50000000 +fptrace +printf
  +ts=/tmp/home_tp40.ts. The bench now supplies PAL field interrupts every 20 ms and logs
  complete outgoing front-panel frames. The loader reset remains at 5.296 s and application
  entry at 7.626 s. This run is still executing, do not restart it unnecessarily.
- Diagnostic V079P is compiling from %TEMP%/Pace2500N_cold_trace_20261120, Quartus 17.0.2,
  seed 5. CPU wrapper has a separate trace_reset tied to full core_reset, so a warm reset
  preserves the frozen instruction/bus trace. TRACE_PC=8003A928 captures the caller of the
  firmware reboot routine. Focused simulation verified trigger, warm-reset retention and
  full-reset clearing. UART MMIO trace omits boot FIFO traffic and serial status/clock
  polling, retaining serial data bytes. No functional controller reply change yet.
- Ghidra 12.1.4 projects still work in re/ghidra. Reports in WSL /tmp/cold_*.txt.
  8003A928 calls 8002A1BC, which sends packet 03 seq 12 00. 80037228 can request it
  for platform events 1B/21, and the runtime fatal handler can also call it. A transport
  reply is accepted by its sequence in 8002B1AC, independently of opcode.
- The model's generic 02 seq 10 replies are malformed for the application's opcode-10
  callback (80029788 copies SIX payload bytes). Opcode 52's app callback 8002A534 reads
  one payload byte, also missing from the current reply. This is an observed protocol
  defect, its role in the reboot has not been proven. Do not equate heartbeat 18 with
  a mandatory data reply: it has no callback in the application's seven-opcode table.
- Repeated V079O hardware runs vary. One fresh run remained in the application for
  120 s with black output and only four GPU completions. Another eventually froze its
  trace after a Guide key. All 227 frozen pages were recovered to
  %TEMP%/pace-cold-20261120/O-tasks-uart.txt and decoded instructions to
  O-frozen-instructions.txt. Latest bus transaction is I2C control A8 at 12006000.
  Last retired PC is 800D3628 (scheduler restoring FETask), not the TLB panic address.
  Exact model halt code has not yet been established. Do not assume E5 from these alone.
- Hardware artifacts are /tmp/cold079o-continue-*, /tmp/cold079o-tasks-* and
  /tmp/cold079o-diag-* on MiSTer. The scripts restore V078 automatically. Read-only
  DDR dumps are in %TEMP%/pace-cold-20261120/O-tasks40.bin and O-tasks80.bin.
  A raw HPS DDR dump can omit dirty CPU cache lines. The task census rejects this
  dump's partially visible created-task links. Saved stacks suggest TASK0 was in
  frontend initialization (800284C3) and FETask in 80024FFF/80028F91, but this is
  incomplete cached-memory evidence.
- Playout was initially stopped and was started for testing. The old EXE in dist dated
  17 Nov 19:17 used the OLD synchronous carousel builder. py-spy proved streams waiting
  behind FirmwareHuffman.encode and Server.carousel. It and its FFmpeg children were
  stopped. The current-source app was rebuilt, installed in dist/PaceChannelBuilder and
  started as PID 54216. Rollback copy is dist/coldboot-app-rollback-20261120-2159.
  huffman_ram now points to original firmware/FLASH_U202.bin; other personal settings
  are retained, with a settings backup in %TEMP%/pace-cold-20261120 (private).
  Both /tune probes delivered valid packets in 0.14 s. A 65-second paced Guide feed
  delivered 50,834,448 bytes, maximum socket read 0.141 s. Cold V079O still produced
  black output with this corrected feed, so the core blocker remains.
- A concrete byte-loss defect is now fixed in rtl/pace_guide_peripherals.sv. The ISR
  clears RX ready before SMNTask consumes its software mailbox. Controller-driven
  bytes now wait for a fresh B2009010 write (the task's receipt); a GPIO edge arriving
  after the corresponding transfer completed cannot start another without new TX data.
  A write during an active transfer stays queued. sim/tb_front_panel_receipt.sv fails
  against original HEAD at the early-advance assertion and passes with the patch.
  Updated full system run /tmp/cold_receipt_run.log uses /tmp/vl_cold_receipt/Vtb_sys,
  +cold +cycles=1600000000 +status=50000000 +fptrace +printf +ts=/tmp/home_tp40.ts.
  It is running alongside the original comparison run. V079Q build sources are prepared
  in %TEMP%/Pace2500N_cold_receipt_20261120; start Quartus after V079P finishes.
- Removed the PC encoder's need for a checkpoint too. FirmwareHuffman.from_file now
  accepts original 2 MiB U202 and uses extract_application_ram.extract plus the
  resident resource at 800FD798 (511 edge pairs, 256 phrases). It never writes a CPU
  checkpoint. Codes and symbols match the initialized-RAM codec exactly. Defaults
  and GUI wording now select FLASH_U202.bin while honoring existing saved paths.
  All 20 Python tests pass, with one pre-existing optional FFmpeg skip.
  The source edits and diagnostics remain uncommitted pending hardware verification.

## 20 Nov 2026 (late) - V079O: loader fixed, application now requests a reset (STOPPED HERE)

- **V079N's failure explained:** the boot monitor on V079N showed model halt **E2**
  (front-panel frame length) at PC 9FC01BDD, 5.5 M instructions - the same as V079H. Frozen CPU
  trace: the loader mid-handshake (W B2009010 byte, B200A000 = 1, ..., = 0). Cause: the link
  model read B2009010 when a transfer *completed*; if the box was preempted between raising and
  lowering the clock, the controller's own transfer (clocking in its reply) completed with the
  box's byte and the box's transfer counted it again. Build-dependent because it depends on
  where interrupts fall. Not related to the A000/A004 read-back.
- **75654dd, V079O** = V079N + link fix: a transfer takes the B2009010 byte when it starts, each
  written byte is counted once, a transfer with nothing newly written only delivers the
  controller's byte. tb_sys: loader exchange (412 frames), 0x12 reset at 5.296 s and application
  entry at 7.626 s unchanged. Built in 42 min (RAM checked first: 5.9 GB free after
  `wsl --shutdown`). Timing: core clocks met; HDMI scaler -1.9 ns as before.
- **V079O on hardware:** flash aligned; the loader now passes (no E2) and the application starts
  (demux set-up at 33.3 s of the capture), but about 10 s later the box restarts completely (loader
  at 43.3 s and 48.8 s, application again at 60.5 s); a front-panel frame with code 0x12 (the
  box's reset request) appears in that window. Screen black throughout; decoder counters 0;
  no halts. Not established whether the link change causes the application's reset request
  (its 0x52/0x18 controller exchange timing out?) or something else - V079M (old link model)
  did not reboot in its 45 s capture. The UART trace still drops serial events, so whole
  frames cannot be rebuilt from it.
- Next: make the trace keep serial frames (e.g. drop B00020B0/B8 and keep only frame bytes),
  rebuild the application's frames before the 0x12, and check them against the controller
  model's replies; also run tb_sys past application entry with a field tick (see below).
- MiSTer left on V078. Builds V079K-O are in /media/fat/_Other/.

## 20 Nov 2026 (evening) - V079N built and tested: REGRESSION, do not use

- PC was rebooted 16:05 (the earlier V079N fit never finished). V079N rebuilt from 7138cfd in
  41 min (fresh RAM). Timing: core clocks met (general[5] +0.088 ns); HDMI scaler -2.427 ns as
  before. RBF: output_files/Pace2500N_V079N.rbf, on the MiSTer as _Other/Pace2500N_V079N.rbf.
- Channel Builder had to be restarted after the reboot (playout took >25 s to listen on 8250).
- **Result: V079N does not reach the application.** Run 1 (no feed at load, then reloaded with the
  feed): the loader ends in its idle loop at 9FC0DE4C/60 (all tasks blocked) right after its
  boot-data-port test; no A000 = 0x73, no warm boot. Run 2: the UART trace and telemetry stop
  at 9.03 s, mid boot-data-port test (B00020B4 = 2); not yet established whether the core
  stopped or only the UART. Flash aligned both times.
- The only RTL difference from V079M (which reached the application and the backdrop loop) is
  B000A000/A004 read-back (pace_section_demux.sv). The sim log (dt14) shows the loader never
  reads A000 and reads A004 only while it is 0, so the read-back should not affect the loader -
  cause unexplained. Next: confirm whether V079M still boots past the loader now (run-to-run
  variation was seen before: V079I/V079K/V079L/V079M behaved differently between runs), and if
  V079N alone fails, find what differs (Ghidra on the loader around 9FC0DE4C waiters, HPS RAM
  liveness check, UART trace ending).
- **Quick check (same evening): the failure is V079N-specific and repeatable.** V079M, loaded
  straight after under the same conditions, boots normally: loader self-test, A000 = 0x73 at
  9.6 s, warm boot 15.1 s, application demux set-up 24.4 s, backdrop set-up 31.3 s. V079N run 3
  stopped exactly like run 2: B00020B4 = 1 at 8.89 s, = 2 at 9.13 s, then the UART trace and the
  telemetry frames stop (last PACE frame PC BFC18EE8, 2.5 M instructions). So the core (or at
  least its clk_sys debug path) stops during the loader's boot-data-port test (B00020B0/B4/B8 in
  pace_guide_peripherals), long before any demux read. Suspect a build/placement effect rather
  than the read-back logic itself; next: HPS RAM liveness check on V079N, compare V079N and
  V079M fitter reports, and rebuild V079N with another seed before changing RTL.
- The MiSTer was left on V078 before the test; V078 was reloaded at the end of the session
  (_Other/Pace2500N_V078_Live.mgl) for normal use.

## Session 19-20 Nov 2026 (continued) - backdrop decoded on hardware; restart loop found (V079K-N)

**State at hand-over:** V079N (commit 7138cfd) was still in the Quartus fitter, started
20 Nov 09:31, left running; it has NOT been tested. The MiSTer runs V079M. To finish:
`quartus_cpf -c -o bitstream_compression=on output_files\Pace2500N.sof
output_files\Pace2500N_V079N.rbf`, copy it and `Pace2500N_V079N_Live.mgl` to
/media/fat/_Other/, `load_core` the MGL (playout/Channel Builder must be running on the PC),
then capture `python3 /tmp/ut.py 120 --all` (tools/mister/mister_uart_trace.py) and screenshots.
Expected if the fix is right: the WD telemetry word shows sequence headers and sequence-end
events counting (top three bytes), the firmware's bit-16 wait succeeds and the Guide backdrop
stays up instead of cycling blue/black/backdrop every ~4 s.

What was found and fixed (all pushed to cold-boot):
- **0411acd, V079K: DMA stop.** Ghidra: the application stops a DMA channel by clearing its
  B0009010 bit (0x80005D30), the loader clears bit 5 ~3 us after starting its 32-byte flush.
  The model ignored the clear; with MiSTer DDR latency the flush completed after the loader's
  B0009130 acknowledge, leaving a pending DMA interrupt -> V079H halted E2 in the loader, V079I's
  application idled. Now a clear stops channel 5 with no completion. (Sim with fast DDR never
  showed it: the flush finished before the stop.)
- **V079L (05f0c92), diagnostics:** UART trace adds demodulator I2C and B0009xxx DMA accesses;
  the CPU trace ring freezes on any model halt. Result: the application passes demodulator
  set-up and graphics DMA, and **the Sky Guide backdrop was decoded on hardware from the
  firmware's own DMA5 feed** (v079l_guide_backdrop_hw.png), but it kept restarting.
- **7138cfd, V079N: demux A000/A004 read back as written.** V079M (decoder ISR traffic removed
  from the UART trace so events are no longer dropped) showed the app sets up the backdrop
  input once (A094=1FFF, A000 bit-5 pulse, A004 0->1, A000=0x1000, B0002144=0x980,
  B0002140=0x41/0x01) and on every later start pulses A000 bit 5 by read-modify-write. A000
  read as 0, so bit 12 (memory input) was cleared, the ES went to the demux, the decoder saw no
  sequence header/end, the firmware's 100-tick bit-16 wait (0x8000F950) timed out and it
  restarted. Telemetry WD now = {seq-end raw, seq-end gated, seq headers, flags es_dma,
  dma_video_es, video_on, es_memory, decoder_flush, still_enable, dec_live, decoder_ready}.

Open items:
- **DMA channel 8 not modelled** (Ghidra, re/app_ch8_users_ghidra.txt,
  re/app_dma_callers_ghidra.txt): 0x8000AD14 fills the video frame buffer with one colour
  (luma 720x288 per field via 0x8000B128, count 0x8700; CbCr interleaved 720x144 via
  0x8000B1E0, count 0x4380; second field +0x80000; B00020C0=0x12, B00020D0=frame base from
  B00020A0/A4/98/9C, B00020C4=1, then DMA ch8 from RAM). Used to paint the video black around
  the backdrop. Each times out (11 ticks). Needs the EMMA frame-store layout mapped onto the
  mpeg2fpga frame store - not started.
- **V079K once halted E5** (demodulator group-4 read at APR >= 128) on hardware; not seen
  since. Earlier Python runs only ever wrote group 4 at 0x00-0x59. Unexplained, timing-related.
- **tb_sys has no video raster**, so the firmware's per-field decoder interrupts never come:
  the sim stops right after the backdrop set-up (22.86 s). Add a field tick to tb_sys before
  using it past that point. Slow-DDR runs (+lat=20 +busy=30) crash the warm boot with an
  exception at 9FC0EE50 (bad sp); not seen on hardware; not investigated.
- HDMI scaler clock (pll_hdmi) fails setup by -2.0..-2.5 ns on V079H-L; core clocks met.
- PC: the RAM held outside processes builds up during heavy WSL use (sims, Ghidra) and is only
  freed by a reboot; builds then take 3-5 h instead of ~1 h. Reboot before a build.

## Session 19 Nov 2026 - the Guide backdrop path a cold box needs (V079H/V079I, branch cold-boot)

- The blue 3 s / black 0.25 s cycle on V079G: the application draws the Guide backdrop by
  feeding its MPEG still (AV command 0x23; provider 0x80020450, 8 KiB blocks) through DMA
  channel 5 to the video decoder (0x8000F890), and waits on (1) the DMA completion interrupt
  (handler 0x80005E28: B0009122 -> clear B0009010 bit, callback, ack B0009130) and (2) decoder
  status group 1 bit 16 after the flush 0x8000FA04 (0x20C-byte zero blocks ending 000001B7),
  enabled alone by 0x8000F950. None of this was modelled; the checkpoint used the host still.
- Modelled (926dc8a): DMA5 pending/IRQ/ack; A000 bit 12 + A004 bit 0 routes DMA5 to the decoder
  as an ES (inferred from the firmware's still set-up: A094=1FFF, A000 bit 5 pulse, A004=0->1,
  A000=0x1000); vld tap "sequence end acted on" -> B0002480 bit 16; host still checkpoint-only.
  sim/tb_mpeg_video +STILL with the firmware-style feed (still once + six padding blocks):
  720x576, picture live, bit 16 on each sequence end -> the Sky Guide picture (no repeats).
- The "stuck flush DMA" seen in tb_sys was a TESTBENCH bug (its arbiter took owner 7 reads as
  writes when the CPU's write line was high); the real top level was right.
- V079H on hardware: halted E2 (front-panel frame) at 5.7 M instructions, right after the loader
  enables interrupt mask 6. Cause: the loader's 32-byte flush DMA completed ~160 us after the
  loader acknowledged it (the demux only takes the DMA input at a broadcast packet boundary), so
  its completion stayed pending into the loader's interrupt enable. Fix: 64-byte input buffer in
  pace_transport_dma (completion = bytes left memory); tb_sys shows the flush complete before
  the acknowledge and the loader continuing. V079I = that fix (build started 09:54).
- V079H timing: HDMI scaler clock setup -2.475 ns (framework pll_hdmi), core clocks met.
- PC trap: builds ran ~3x slower with <1 GB free; `wsl --shutdown` after sims before building.

## Session 18 Nov 2026 (evening) - cold boot runs on the MiSTer (V079E, branch cold-boot)

- V079C/D held on the boot monitor: the guest RAM clear's first 8 DDR writes wedged the HPS
  port (busy for good). The clear raised write only when the port was not busy, so a stalled
  write could be withdrawn; it now holds each Avalon write until accepted (7d4ee1f). Found with
  the boot monitor's spare rows (start-up flags, DDR busy run, writes, status, last download).
- sim/emu: simulation of the real emu top level (stand-ins only for PLL, hps_io/menu, MPEG
  decoders) with an Avalon DDR model; covers download, RAM clear, hold release, loader start.
- MiSTer trap: after one ssh `reboot` every download landed +16 bytes in DDR (even V078 halted);
  a second reboot fixed it. Check with tools/mister/flashcheck.py before blaming the core.
  Screenshots: `screenshot <label>` via /dev/MiSTer_cmd (never hand-start the menu program).
- V079E on hardware: flash aligned, RAM cleared, loader -> 0x12 -> application, first OSD screen
  ~40 s after load, then a blue plane. With Channel Builder running the firmware cycles every
  ~1.5 s between tuning the EPG transponder (11.778 GHz, audio 0x288) and "video 5FFF, freq 0";
  keys change the picture. Next: why it loops (home transponder/service data a cold box expects).
- Timing V079E: setup and hold met on all core clocks (seed 5).

## Session 18 Nov 2026 (afternoon) - cold boot reaches the application in RTL (branch cold-boot)

- `tb_sys +cold` now boots the genuine loader from BFC00000 to the application with no host
  help: both self-tests pass (boot data port B00020B0, demux fed by DMA channel 5 from flash),
  front-panel exchange (0x44 polls to frame 0x1F, as the Python run), image CRC, `03 20 12 00`
  at 5.3 s, warm reset, APPLICATION ENTRY BFC2048C at 7.6 s, RAM application at 13 s, EEPROM/I2C
  start-up, 4 bpp first screen at 21.8 s, then the Guide's own 8 bpp display list at 23.1 s
  (same CLUT/field buffers as the checkpoint). Commits 971299c, d0cdd5c; see re/COLDBOOT_PLAN.md.
- Demux generalised to guest-programmed rings (B000A120 page, indirect fields 0/2/3), trailer =
  filter number, no IRQ-enable gating; sim/tb_transport vectors regenerated and passing.
- Scan-out: 1/2/4/8 bpp display lists (was 8 only: a cold boot's first screen would have stopped
  it with error C1). sim/tb_guide_video601 fixed (raster ports) and passes 8 and 4 bpp.
- Branch default is now "Boot: Cold from flash" (status bit 7 = 1 selects Checkpoint).
  `Pace2500N_V079C_Live.mgl`: FLASH + EEPROM save + live ring only.
- NOR identify modelled (AT49LV1614 codes per the board drawing; the user's ST-based Thomson
  board uses M29W160ET, which the 2500N loader's table does not list). Open: the first-stage
  application runs uncached from flash at
  ~1.7 M instr/s in the model (7.6 -> 13 s); hardware test of the build.

## Session 18 Nov 2026 - the loader handoff found (cold boot work started)

- User: bookings/settings must persist like a real box (EEPROM read at boot), so the core must
  cold-boot from flash instead of resuming the checkpoint. Chose to hunt the real loader ->
  application mechanism (no declared host jump). FOUND: it is a warm reset requested with
  front-panel command 0x12; the genuine loader then jumps to the application on its second boot.
  Details and simulator proof: `re/APPLICATION_HANDOFF_INVESTIGATION.md` (top section).
- The current checkpoint (RAM.bin/STATE.bin) was made with a host jump into the application,
  two host RAM edits (A/V default 80054F84, window root ready 80430A28) and a firmware-formatted
  blank EEPROM - see `re/GUIDE_DIAGNOSTIC_CHECKPOINT.md`. A real cold boot replaces all of it.
- V078 EEPROM persistence: firmware writes reach EEPROM.bin, but bookings live in the Guide's RAM
  list loaded at a cold start, so they only come back once the core cold-boots.

## Session 17 Nov 2026 (night) - speed, stability, stable event ids, 48 channels, EEPROM save

- LISTINGS BUILD WAS 16-21 s (home) / 1.3 s (channels): `FirmwareHuffman.encode` tried every
  phrase at every offset (98 M startswith). Now phrases indexed by first byte, costs not strings,
  cache: identical output (308 strings checked vs the old encoder), 35x faster; home tables 0.3 s.
- The build ran in the session thread holding `_si_lock`: a channels-transponder session waited
  for any home rebuild (7-13 s before the box picked PIDs after leaving the Guide) and a playing
  channel stalled ~1.3 s each minute (> the core's 0.67 s ring prefill). Now `Server.carousel`
  returns the newest finished carousel at once and rebuilds stale ones in a background thread;
  `_keep_carousels` builds both transponders every 20 s from start-up.
- Measured after: channel change -> programme data 0.5-1.3 s after the tune (new log line
  "<channel>: programme data N s after the tune"); leaving the Guide -> PIDs at once. ffmpeg
  starts use `-probesize 262144 -analyzeduration 500000` (~0.5 s off Plex starts). The loudness
  normaliser costs 0.2-1 s more but was asked for, so kept. IPTV (HLS) starts take 4-7 s
  (segment fetch; `-live_start_index -1` was within noise, not used).
- A programme whose ffmpeg run fails part way now retries from the schedule position after a
  2 s gap (3 tries per programme) instead of black for the rest of the slot. BBC1's
  "Children's BBC 1989.mpg" died twice today with "Error submitting a packet to the muxer";
  a full 5380 s run through the same command passes, so it is not one bad spot in the file.
- EVENT IDS were each programme's place in the day: an IPTV guide refresh moved bookings onto
  other programmes (a phantom "Count Duckula 10.38pm"). Now `event_ids()`: (mjd % 22) * 1440 +
  start minute + 1, next free id on a clash; kept < 0x8000 (ids of ~38000 were seen while
  banner tests failed - not proven to matter, but the firmware may hold them signed).
- CHANNELS TRANSPONDER LISTINGS: (a) none at all -> the box showed the banner over black and never
  selected PIDs, and stayed wedged even after data came back (needed a core reload); (b) the full
  current blocks -> the box waited ~10 s on them before retuning for the Guide; (c) final: only
  the home sections (byte-identical, same versions) that hold now and next, plus their synopsis
  sections. Guide entry still retunes ~10 s after TV Guide (the Guide draws at once; only the
  music waits) - looks like the firmware's own timer when it already holds the listings.
- Box wedge seen twice (banner over black, stale now/next, no PID selection for any channel;
  core streaming fine at 778 kB/s, 0 underruns): (a) above, and once after a playout restart that
  changed every listing version (event-id change) while the box was acquiring. Not reproduced by
  rapid channel changes or Guide exit + immediate typing. Core reload clears it.
- IPTV guides: `iptv_guide` now takes the first candidate WITH programmes: the UK guide iptv-org
  lists for tvg_id, then the Pluto link id (they differ for some channels), then another
  region's guide. Line-up: +40 official IPTV channels with listings (105, 107-125 ent, 302-306
  movies, 401-403 sport, 451-453 music, 501-505 docs, 603-606 kids); 48 TV + 18 radio. Backup
  `roms/lineup_mock.before-more-iptv.json`. Married with Children, The Nanny, That's 70s/80s
  have no guide anywhere (Live TV). SIDs follow line-up order, so deleting a channel in the
  middle renumbers later services (bookings follow the SID).
- Key injection: the first key on a new uinput device is often lost - /tmp/mister_keys.py on the
  MiSTer now sends a Left Shift warm-up first. Several earlier "banner reminder fails" results
  were the lost Enter; the user confirms banner reminders work.
- EEPROM SAVE (core V078, `rtl/pace_eeprom_save.sv`, MiSTer slot S1 "EEPROM save"): bookings are
  the firmware's /eeprom/book file (o-code 9FC7DB9C: open/read/write, 76 bytes x <= 50; 19
  readers, 12 writers), so a persistent EEPROM keeps them. EEPROM BRAM made true dual-port
  (port A unchanged for the firmware, sharing one address between the I2C read pointer and the
  commit - they never overlap; port B for the saver). Blank (all-FF) file is filled from the
  checkpoint EEPROM; otherwise loaded with the guest held; changed 512-byte blocks written back
  after ~0.2 s of no writes. Testbench `sim/eeprom_save/tb_eeprom_save.sv` (iverilog): PASS.
  `Pace2500N_V078_Live.mgl` mounts `games/Pace2500N_GUIDE/EEPROM.bin` (S1) first;
  install_relay.sh creates it blank. QUARTUS: the behavioural 64 KiB array was "uninferred"
  (read-during-write, then "asynchronous read") and fell back to registers - synthesis hung or
  ran out of memory; now an explicit altsyncram BIDIR_DUAL_PORT M10K (init rom/checkpoint_eeprom.mif,
  generated from the .hex by tools/export_fpga_checkpoint.py), behavioural model kept for
  simulation (`ifndef ALTERA_RESERVED_QIS`). V078: 442/553 RAM blocks, core clocks met, HDMI -2.24.
- HARDWARE (V078): blank file filled from the checkpoint EEPROM at first mount (layout identical,
  plus a new "favchn" file the firmware created); a grid booking changed 327 bytes in the file;
  after a core reload the booking bytes were still in the file BUT the planner was empty and the
  firmware then rewrote /eeprom/book (new timestamp in its directory entry at 0x1FD0, booking data
  zeroed). The Guide keeps bookings in RAM, loaded from /eeprom/book at a cold start; the core
  resumes a RAM checkpoint taken after that load, so it holds an empty list and saves it back.
  Persistent EEPROM alone does not restore bookings - needs a decision (user) on restoring the
  Guide's booking list into RAM at resume, or a cold boot.

## Session 17 Nov 2026 (late night) - reminders from the Guide grid fixed

- CAUSE 1, the refusal ("The reminder can't be set for this programme"): the Guide's o-code
  (function at 9FC79F01, listed with the reference o-code table: `re/reference_goretrotv/tools/
  ocode-disasm.py` opcodes, scratch decoder synchronised on 9FC7A04D) calls native (12,0x16)
  = 800C66D0 into a 0x17C-byte details buffer and tests details +0x2C at 9FC79FCC. 800C9F58
  copies that from the stored record +4 = the title descriptor's theme byte (our r+10), which we
  sent as 0. Refused only if +0x2C == 0 AND o-code 9FC75AFB(item) == 0 AND row type != 0x10.
  FIX: title records carry Sky's theme byte = genre category << 5 (tvheadend's skyuk table:
  0x40 Kids, 0x60 Ent, 0x80 Music, 0xA0 News/Doc, 0xC0 Movies, 0xE0 Sports; same 3-bit code as
  SDT 0xB2), from the channel genre (radio 0x80). Decompile: `re/reminder_details_ghidra.txt`
  (Ghidra 12.1.4 - the 11.4.2 one cannot open the project; `re/scripts/DecompileMips16.java`
  sets ISA_MODE and makes MIPS16 functions where none exist).
- CAUSE 2, bookings vanished after leaving the Guide: the channels transponder sent cut-down
  now/next title sections under the same table/extension with a different (content) version,
  so tuning a channel replaced the box's full block and the Guide dropped bookings whose
  programme had gone. FIX: the channels transponder carries the current and next six-hour
  blocks as the very same sections (checked: 36 of 36 byte-identical to home ones). Side
  effect: banner Search Time now shows the real programme after next (was "0:00am").
- Verified on hardware: grid Select adds to the Personal Planner (BBC2 Red Dwarf, Retro Toons
  Count Duckula, Tiny Pop Sunny Bunnies), the firmware's REMINDER CLASH screen for overlaps,
  booking kept after leaving the Guide for a channel and returning. Selecting the programme on
  air goes to the planner without adding (expected).
- Reminder FIRES: 7:12pm "Personal Planner - Reminder / This programme is about to start /
  Sunny Bunnies 7:12pm Tiny Pop"; Select tuned Tiny Pop; the 7:14 Count Duckula one followed and
  Select tuned Retro Toons. OPEN: banner look-ahead Select ("Press SELECT to set reminder")
  returns silently and adds nothing, even with no clash (Super Mario 7:39 Retro Toons). The
  user believed banner reminders worked earlier - none showed in the planner here. In 800C66D0
  the record-type-2 path (+0x1D == 2, mask 0xBC read) never fills details +0x2C, so that route
  depends on o-code 9FC75AFB / the row type; the banner o-code is not decoded yet.
- Seen once, not chased: after leaving the Guide the box retuned 12207 with no PIDs (black
  BBC2) - log "guide data only (no channel tuned)" with no follow-up tune.

## Session 17 Nov 2026 (night, later) - IPTV guides for any channel; genre index versions; rc3

- GUIDE INDEX: `iptv_guide_index()` (pace_channels.py) builds iptv-org channel id ->
  (i.mjh.nz XMLTV url, guide id) from iptv-org's guides.json (site i.mjh.nz, site_id
  `Path#id`; ~25 MB, 3,066 keys kept, UK guide preferred), cached weekly as
  `%APPDATA%\Pace2500N\iptv_guides.json`. `iptv_guide(cfg)` order: line-up `epg`, Pluto link,
  then `tvg_id`. `iptv_playlist()` now keeps `tvg-id`; the picker stores it as `tvg_id` and has
  a *Listings* column (UK official: 98 of 170 have a guide). After adding, the Playout log says
  where the guide data comes from.
- Tiny Pop 602 (`tvg_id` TinyPop.uk@SD -> Plex/gb) verified on hardware: Info "Jeremy and Jazzy
  Compilations" + synopsis, All Channels and Kids rows full, grid Info synopsis for Sunny Bunnies.
  Line-up backup: `roms/lineup_mock.before-tvgid.json`.
- BUG FIXED: the genre and A-Z index sections (0xC1, PID 0x52) had a fixed version 0, so the
  box kept the Kids index from before Tiny Pop had listings and the Kids page showed only
  now/next for both channels. Index sections now carry one content-derived version per
  index (all its sections). All Channels was fine (titles already had content versions).
- Selecting a future programme in a genre grid still says "The reminder can't be set" (known).

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
  (2023).
- IPTV GUIDE DATA: `XMLTVGuides` (pace_channels.py) fetches XMLTV (gz or plain), caches per URL
  (refresh 3 h, retry 10 min). LiveChannel uses line-up `"epg": {url, id}`, or for jmp2.uk/plu-<id>
  links Pluto's UK guide https://i.mjh.nz/PlutoTV/gb.xml.gz (~16 h ahead). Programmes become the
  listings, synopses (sub-title + desc) and now/next; gaps are "Live TV". Verified on hardware:
  KIDS page lists 601 (genre 2 = Kids confirmed), real cells, and Info shows "Danger Mouse: The
  Day of the Suds...".
- PICKER: Channel Builder **Add IPTV** opens `IPTVPicker` (pace_builder.pyw): iptv-org country
  list via `pc.iptv_playlist()`, search, "Official sources only" (OFFICIAL_IPTV_HOSTS: Pluto,
  Amagi, MediaTailor, Samsung, Wurl, BBC, Plex...; UK list: 170 of 308), genre from group-title,
  number in GENRE_BLOCK (601 Kids, 301 Movies, 401 Sports, 451 Music, 501 News, 101 Ent, 901
  Specialist; never 800-899), then an ffprobe check logged. Headless smoke test passed.
  Hardware: 602 Tiny Pop (Amagi, needs -extension_picky 0) plays, 782 kB/s, 0 underruns.

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
  Verified: 6 Movies, 3 Entertainment, 4 Music & Radio, 2 Kids (1 Specialist, 5 News & Docs,
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
  including anamorphic sample aspect, into the 720Ã—576 4:3 PAL raster. The
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
  PIDs `0x0700â€“0x0763`. PC playout transcodes the selected public stream to
  48 kHz stereo MP2 at the television loudness target. Channel Builder saves
  stations in the line-up's `radio` array. The preset list is opt-in.
- v0.7.4 displayed stations 801â€“809 in the firmware's Music & Radio grid.
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
- **Likely SoC family:** NEC EMMA / ÂµPD6103x, possibly **ÂµPD61032** (NDS VideoGuard variant); **exact Pace board chip marking not independently confirmed**. NEC references include the September 1999 ÂµPD6103x product documentation. A detailed NEC hardware register map has not been found.
- **CPU:** Big-endian MIPS, using both standard 32-bit instructions and **MIPS16** (not microMIPS). ISA changes, branch-delay slots, exceptions and cache effects matter. Exact VR4110-compatible details require confirmation.
- **Firmware:** original JTAG dumps `FLASH_U202.bin` and `FLASH_U203.bin`, **2,097,152 bytes each**, in `firmware/` of v0.4.2. U202 SHA-256: `32f6b2e84d0c4c4ec280a72f2d080e4b6fa5e68e8438ef712f34f97f63d38c7f`; U203 SHA-256: `7832d619b63e369bdd4a0f3de8dd73c98a99285d96c94a8bb0a39fe829ce1f40`.
- **Flash banks:** differ by 30 bytes, confined to `0x1A0000`â€“`0x1A001F`. Original dumper said this represented dual OTA-update banks. The 128 KiB bootloader at `0x000000`â€“`0x01FFFF` matches both; original dumper zeroed four Digibox serial bytes at `0x1FFF8`.
- **Boot:** first actual reset instructions at U202 offset `0x000008`: `3C08BFC0 25080408 01000008 00000000` (`lui/addiu/jr/nop`), jumping to `0xBFC00408`. Application jump code at offset `0x2002C` points to `0xBFC2048C`.
- **MiSTer hardware:** DE10-Nano, analogue RGB to a CRT TV. Use **625-line, 50-field/s interlaced timing, 15.625 kHz horizontal** (usually described as **576i/50** in active-picture terms), **not 480i/60** or 240p. The generated sync is still an approximation and must be verified on the real CRT. Exact native chip video modes and assets have *not* been extracted/verified.
- **Upstream public FPGA reference:** `https://github.com/MiSTer-devel/Arcade-KillerInstinct_MiSTer`. This has a substantial synthesizable **MIPS III** VHDL CPU, but the current Pace project **does not instantiate it**. Only its MiSTer `sys/` board shell/pin configuration is reused. Its CPU is not a drop-in solution because Pace needs MIPS16 and NEC-specific differences. Respect upstream GPL licensing.

**Original source documentation:** `flashdump_PACE2500N.zip` with `info.txt`, `PACE2500N_Bootloader.zip`, `DigiboxTool.zip`. The earlier `Pace2200sm_*.pdf` and `Pace2200sch_*.pdf` are for the **different Pace 2200 ST20 system**; do not assume those schematics apply to the 2500N.

## 3. Confirmed reverse-engineering evidence (software probe only)

The supplied `probe_strict.json` records execution in an **experimental Python CPU interpreter**, not execution on FPGA:

- **3,178,986 interpreted instructions** until an unknown 16-bit MMIO read, `0xB0000002`, at `PC 0xBFC01E1C` in MIPS16 mode.
- **MIPS32 â†’ MIPS16** transition: instruction at `0xBFC00578` (`JALX`) enters `0xBFC01E18`.
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

1. Earlier v0.1â€“v0.2 projects were standalone FPGA diagnostics, not normal MiSTer menu cores. v0.3 added a fake Guide-like graphics prototype and a firmware viewer; that visual prototype was **rejected** because the real firmware must generate the UI.
2. v0.4 provided a standard MiSTer `emu`/`sys_top` shell, an incomplete custom MIPS32/MIPS16 executor, ROM, DDR3 bridge and 576i CRT boot monitor.
3. **v0.4 initial Quartus failure:** `Error (10028): Can't resolve multiple constant drivers ... Pace2500N.sv(83)`. The error was caused by connecting the `hps_io` **output** `.sd_buff_wr` to `1'b0`. **v0.4.1 fixed this** to `.sd_buff_wr()` (unconnected). This is the one confirmed compiler issue addressed in that release.
4. User's **v0.4.1** Analysis & Synthesis ran for **around 90 minutes without reaching the fitter**. This is the current observed performance problem. It was **suspected**, not proven, that multiple independently addressed reads of a 32,768-word Ã— 32-bit firmware ROM triggered inefficient synthesis/multiplexer expansion.
5. **v0.4.2 Lean** was produced to address that suspicion: ROM changed to a single synchronous inferred M10K port and video hex browser removed. **v0.4.2 synthesis and final FPGA resources/performance are not yet tested.** The user requested this handoff **before attempting the new build**.

Do not describe the v0.4.2 fix as verified until an A&S report shows inferred memory and realistic runtime/resource counts.

## 5. Current v0.4.2 project files and implementation

Archive root after extraction: `Pace2500N/`.

```text
Pace2500N/
â”œâ”€â”€ README.md
â”œâ”€â”€ CHANGELOG_v042.txt
â”œâ”€â”€ QUARTUS_FIX_v041.txt
â”œâ”€â”€ build_windows.bat
â”œâ”€â”€ Pace2500N.sdc
â”œâ”€â”€ files.qip
â”œâ”€â”€ firmware/
â”‚   â”œâ”€â”€ FLASH_U202.bin       # genuine full 2 MiB bank, supplied
â”‚   â””â”€â”€ FLASH_U203.bin       # second genuine 2 MiB bank, supplied
â”œâ”€â”€ rom/
â”‚   â”œâ”€â”€ bootloader_words.hex # genuine first 128 KiB of U202, BE 32-bit words
â”‚   â”œâ”€â”€ font8x8.hex
â”‚   â””â”€â”€ monitor.hex          # DIAGNOSTIC MONITOR text, not Sky firmware UI
â”œâ”€â”€ rtl/
â”‚   â”œâ”€â”€ Pace2500N.sv        # MiSTer emu top, HPS file upload and DDR interface
â”‚   â”œâ”€â”€ pace_bootrom.sv      # single-port synchronous M10K ROM
â”‚   â”œâ”€â”€ pace_firmware_cpu.sv # experimental MIPS32/MIPS16 executor
â”‚   â”œâ”€â”€ pace_pal576i.sv      # 625/50 RGB interlace timing (simplified sync)
â”‚   â””â”€â”€ pace_boot_monitor.sv # live status screen (PC, instruction, MMIO, etc.)
â”œâ”€â”€ sim/
â”‚   â””â”€â”€ tb_boot.sv           # WARNING: stale; see section 7
â””â”€â”€ tools/
    â”œâ”€â”€ build_project.ps1   # downloads/copies KI sys/, creates .qpf/.qsf
    â”œâ”€â”€ build_project.py    # alternative Python generator
    â”œâ”€â”€ make_monitor.py
    â”œâ”€â”€ pace_probe.py       # software interpreter
    â””â”€â”€ verify_firmware.py  # reproducibility/integrity checks
```

**HDL-specific facts:**

- `rtl/Pace2500N.sv` uses the standard MiSTer `emu` ports from `sys/emu_ports.vh`, `hps_io`, and the `sys/` support files sourced from Killer Instinct. The KI **CPU itself is not used**.
- `rtl/pace_bootrom.sv` declares `(* ramstyle = "M10K" *) reg [31:0] words [0:32767]`, initialises it from `rom/bootloader_words.hex`, and has **one registered read port**.
- The CPU accesses the protected flash region via ROM, and the remainder of U202 via a MiSTer DDR3 upload if the full `.bin` has been selected. It also uses DDR3 for emulated RAM. **The correctness of byte lanes, address translations, DDR3 request/ready sequencing and memory map is unverified on MiSTer.**
- Top-level video drives `CLK_VIDEO = CLK_50M` and a 12.5 MHz pixel enable from `pace_pal576i.sv`. Nominal raster is 800 samples per 64 Âµs line, 625 lines/25 frames and 50 fields/s; 640Ã—576 active sample layout with alternating fields. PAL equalising/serration pulses are **not** complete or broadcast-exact.
- The RGB picture is **only a diagnostic monitor**. There is **no** actual NEC EMMA overlay/OSD decoder, MPEG-2 video/audio output, TS demux, tuner, smartcard, Sky Guide graphics renderer, or firmware-controlled output plane. Even a successful core build will *not* show Sky Guide yet.
- The CPU lacks comprehensive CP0, exceptions, TLB, cache, interrupts and complete MIPS16. The `CACHE` opcode is explicitly treated as a no-op; MMIO reads may halt or return guesses. These shortcuts can change real firmware execution.

## 6. Build and MiSTer deployment â€” intended procedure, NOT yet proven

1. Extract `Pace2500N_RealFirmwareBoot_v042_Lean.zip` in a fresh Windows folder.
2. Run `build_windows.bat`. It calls `tools/build_project.ps1`, downloads the public Killer Instinct repository if needed, copies `sys/`, and generates `Pace2500N.qpf` / `.qsf`. Requires an Internet connection for the automatic download, or use `tools/build_project.py --ki <existing KI checkout>`.
3. Open `Pace2500N.qpf` in **Quartus Prime Standard** for Cyclone V. **Run Analysis & Synthesis only first**. Record duration, RAM Summary/M10K use, ALM/register count, memory-inference warnings and the last progress messages. Stop/report if it behaves like v0.4.1.
4. Only after A&S succeeds, run full compilation, producing `output_files/Pace2500N.rbf` (assuming project QSF settings and tool versions allow it).
5. Copy `Pace2500N.rbf` to `/media/fat/_Other/` (visible as **Other** in the MiSTer menu). Optionally place `FLASH_U202.bin` at `/media/fat/games/Pace2500N/FLASH_U202.bin` for convenient browsing; this is a convenient storage path, **not a mandatory auto-load convention**.
6. Load **Other â†’ Pace2500N**, then press **F12**. The **actual v0.4.2** `CONF_STR` is:

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

- **Current candidate:** `Pace2500N_RealFirmwareBoot_v042_Lean.zip` â€” project source and both full flash dumps.
- **Previous build:** `Pace2500N_RealFirmwareBoot_v041_QuartusFix.zip` â€” had fixed multi-driver output; user's A&S took about 90 minutes without reaching fitter.
- **Original firmware dumps:** `flashdump_PACE2500N.zip`.
- **Original protected bootloader:** `PACE2500N_Bootloader.zip`.
- **Historic JTAG dump program/manual:** `DigiboxTool.zip`.
- **Software trace history:** `pace2500n_stage4_cpu_probe.zip`, and `probe_strict.json` / `probe_experimental.json` inside the v0.4.2 project.
- **Upstream shell / alternative CPU:** https://github.com/MiSTer-devel/Arcade-KillerInstinct_MiSTer
- **NEC product overview found in earlier research:** https://tvsat.com.pl/PDF/U/UPD61032_nec.pdf â€” product-family description, **not** a confirmed Pace 2500N register-programming manual.

---

**Resume instruction:** Treat this handoff and the newest project source as the working baseline. The user's immediate priority is a **reasonably fast and reproducible Quartus build that shows real firmware-execution progress on a PAL CRT**. Start by fixing the v0.4.2 stale testbench and validating synthesis; don't spend another turn creating a mock Guide or restating plans.
