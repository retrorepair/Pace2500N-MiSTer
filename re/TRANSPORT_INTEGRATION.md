# Transport integration: revised handoff and implemented contracts

8 November 2026. Applies to the attached `handoff _1_.md`. The attachment is
design input, not an instruction to execute its sample URLs. Firmware execution
remains entirely in FPGA, preserving the user's architecture choice.

## Decisions

| Handoff proposal | Revised implementation |
| --- | --- |
| HPS runs yt-dlp and transcodes live | PC produces/caches media; MiSTer ARM transfers bytes. Local cached files first. |
| stdout goes to an AXI buffer | Existing Main/MGL IOCTL index 3 loads a bounded TS replay area through the existing DDR bridge. A continuous live feeder remains later work. |
| Add an arbitrary 27MHz FIFO clock | Use the existing 50MHz core/DDR interface and ready/valid byte pacing. The DDR bridge handles its existing clock crossing. |
| Nulls prevent decoder PLL unlock | Null packets preserve transport framing/byte budget. They carry no PCR and cannot establish decoder lock. |
| Audio 0102/video 0200 are NEC requirements | They are defaults in the optional PC producer, explicitly signalled in PMT; all three elementary/PMT PIDs are configurable. |
| OpenTV always uses PID 0030 and DSM-CC trees | Native titles use rotating title PIDs and private section/table formats. SI namespace descriptors and clock/acquisition ordering matter. A generic DSM-CC feed is insufficient. |
| Hardcoded web schedule and URLs | Aware ISO timestamps, half-open slots, source offsets, cached files, provenance, overlap validation and bounded programme duration. No placeholder downloads. |
| Send programme media directly to current core | Current FPGA consumes PSI/SI sections. MPEG video/audio PES decoders are still absent. PC producer output is prepared and tested separately. |

## Implemented FPGA path

`Pace2500N_Transport.mgl` loads the same disclosed 200M Guide checkpoint plus a
packet-aligned TS file at index 3. This is still a checkpoint diagnostic with
the two existing RAM interventions, not a protected-loader cold boot.

1. IOCTL stores at physical HPS DDR `0x33000000`, maximum 1 MiB. This is outside
   guest RAM `0x30000000..0x30ffffff`, ROM `0x32000000..0x323fffff` and the
   platform scaler/video areas at `0x20000000` / `0x24000000`. Oversize files
   are not allowed to write past the replay region and are not enabled.
2. File length must be a nonzero multiple of 188. The CPU is held during file
   transfer, as with existing checkpoint downloads. Stream parser state is
   discarded on a replacement transfer; guest filter/interrupt state remains.
3. `pace_ts_replay.sv` fetches via the existing DDR arbiter, handles packet starts
   at both 64-bit alignments, loops at the exact file length and honours byte
   backpressure. Nominal maximum is 1 Mbit/s (one byte per 400 core clocks).
   Parser/DDR stalls may lower that rate. There is no PCR/PLL claim.
4. `pace_section_demux.sv` implements 32 PID channels, per-channel partial
   section RAM, adaptation/PUSI/pointer handling, continuity and duplicate
   checks, length bounds and MPEG section CRC (including TOT; TDT has none).
   TEI/scrambled/malformed input cannot deliver a section.
5. Thirty-two logical match units are packed into sixteen register pairs:
   unit `2*n` uses the low halfword of pair n, unit `2*n+1` the high halfword.
   Eight byte criteria compare section offsets 0,3,4,5,6,7,8,9. A PID channel
   owns its routing bitmap at pair `channel&15`, word `8+(channel>>4)`;
   bitmap bit u selects logical match unit u. Unrouted/rejected sections do not
   DMA or IRQ. Multiple channels can independently request the same PID.
   Rules/routing occupy one synchronous 256x32 M10K. A 256-cycle configuration
   phase restores checkpoint seeds or clears a software block reset; CPU MMIO
   acknowledgement and TS ready are held until it completes. This removes
   about 4800 flip-flops and their wide read muxes from the congested design.
6. Completed records go into physical guest RAM `0x007a0000 + channel*0x3000`,
   followed by a zero trailer. Bytes wrap circularly, including when table_id
   occupies the ring's final byte and section_length occupies its first two.
   The guest-programmed indirect limit (index `channel*4+2`) bounds available
   circular space. Full rings and
   pending completions drop repeats, counted in telemetry; they do not overwrite
   unread data to fabricate progress.
7. Payload writes complete before write-pointer publication and section status.
   Guest LISR reads status `B000A0B8` & enable `B000A0D8`, clears status by
   writing zero bits, selects `4000 | channel<<2` at `+124` and reads the 21-bit
   write pointer at `+128`. Enable is write-one-to-set; command busy reads zero.
   Status/enables support big-endian byte/halfword accesses. Demux IRQ is the
   existing EMMA interrupt-controller bit `0x01000000`.
8. MMIO replies are registered in `pace_mmio_response.sv`, breaking the long
   register-decode-to-CPU-writeback path. It preserves an accepted response
   across file-transfer hold, preventing a duplicate write when the CPU resumes.
   `pace_ts_load_tracker.sv` checks sequential two-byte IOCTL writes with an
   eight-bit packet remainder counter, avoiding a large combinational divider.
9. The OSD option **Diagnostic RF lock** defaults to **From TS**: after three
   packets from an explicitly loaded file, LSI group 3 APR 11 supplies `0x3f`.
   **Off** retains the v047 no-RF response. This is a declared functional
   acquisition model, not evidence of physical tuner/demodulator accuracy.

Seeds are exported from the actual guest-written checkpoint filter state by
`tools/export_demux_checkpoint.py`, not chosen to make a fixture pass. Initially
channels 22/23/24 ask for PIDs 0014/0011/0010. This application ABI is separate
from the older boot-self-test scaffold in `pace_probe_demux.py`.

UART v048 fields: `WA` high16 graphics completions, low16 delivered sections;
`WD` keyboard make/break count and remote frames; `RD` last key and scanout
underruns; `GUESS` accepted transport packet count. Counters display low bits
where packed. HALT retains the existing combined CPU/model/GPU/video status.

## PC tools

Create or inspect the deterministic, explicitly synthetic fixture:

```text
python tools/sky_streamer.py fixture --output re/transport/diagnostic.ts
python tools/sky_streamer.py inspect re/transport/diagnostic.ts
```

The four-second fixture is 500080 bytes, 2660 packets, SHA256
`51756ae05ef1af52c6b100783771fc11d014e5d2469303e6973f8cd9fc6dffcf`.
It repeats TOT (fixed 2002-09-01 12:00 GMT), NIT, SDT, BAT, PAT and empty PMTs,
with two TEST services, guide-visible B1 flags 06, off-air B2 rows and null
padding. It advertises no imaginary A/V streams and carries no OpenTV titles.
It does not claim historical channel accuracy.

To add original-firmware Huffman-coded B2 rows and A3/B5 title records:

```text
python tools/sky_streamer.py fixture --huffman-ram re/fpga_guide_checkpoint/RAM.bin --output re/transport/guide_titles.ts
```

The partial title fixture is also 500080 bytes, SHA256
`b8b08b1bb7ae9799e16f1a6c6f37ed47b8a043ef410b810a3d341417eea03190`.
It adds PID36/A1/A2, IDs0BB8/0BB9, MJDCD26 and three synthetic programmes per
service. Low title-table bits select the six-hour block: noon belongs in A2,
accepted by the guest's A3/FE mask. B2 row text uses the same native codec.

The launcher selects the fuller synthetic broadcast:

```text
python tools/sky_streamer.py fixture --huffman-ram re/fpga_guide_checkpoint/RAM.bin --full-day --index --output re/transport/guide_full_day.ts
```

It contains48 hourly programmes across two services, all four title blocks,
and34 C1 alphabetical/genre index heads onPID52. Indices reference actual event
IDs and are paced after the title wave with a null-packet gap. Empty alphabetical
heads are explicitly transmitted. File size remains500080 bytes, SHA256
`fb78a17240da590f2254d189ede5893905a1a942c87e923baeecc5dc254c355f`.
Encoding/CRC/reference bounds are tested; full-guest display remains under
validation. No title bytes are poked into guest RAM.

An optional late-subscriber notification diagnostic adds `--index-updates` and
writes `guide_updates.ts`. It cycles DVB versions after each full index pass,
four heads per wave. All34 heads have at least two versions per file. SHA256
`c981d8662dbdf0a6dc4ea502ad50ea85db5a936e1f53c8ae33a8775c449a38c7`.
This is a labelled synthetic update test, not evidence of authentic Sky timing.

The separate PC media producer uses this JSON schema, with media cached by the
operator beside the JSON. It does not obtain or substitute web content:

```json
{
  "provenance": "Synthetic local test, replace with documented source",
  "programmes": [
    {
      "title": "Local test clip",
      "start": "2002-09-01T12:00:00Z",
      "end": "2002-09-01T12:30:00Z",
      "file": "local_clip.mkv",
      "offset_seconds": 120
    }
  ]
}
```

```text
python tools/sky_media.py schedule.json --at 2002-09-01T12:05:00Z --check
python tools/sky_media.py schedule.json --at 2002-09-01T12:05:00Z --seconds 30 --output media.ts
```

The second command seeks to 420 seconds, outputs at most 30 seconds, maps both
video and audio, and preserves PCR/DTS mux buffering. Output is MPEG2 720x576
25fps, SAR16:15, MP2 stereo 48kHz 192kbit/s, nominal 5Mbit/s TS. The default
PIDs are choices, not fixed hardware contracts. Programme restarts signal
transport discontinuity. Logs use stderr; stdout is exclusively transport
bytes. Child processes are terminated/reaped on interruption or timeout. Missing
sources, gaps and exhausted clips stop with an explicit error instead of
silently playing unrelated media. No shell commands are assembled from titles.

The media producer uses TSID 1 because FFmpeg's muxer rejects TSID 0. The current
independent SI diagnostic uses TSID 0. These are separate tests, not a combined
broadcast. A future A/V/SI mux must use a single coherent set of identifiers.

The installed static FFmpeg 7.0.2 crashes probing even its own minimal MPEG-TS
baseline on this machine. An isolated build was installed under WSL
`/opt/pace-ffmpeg81/bin`, without replacing the existing tools. Download asset
`ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz`, reported version
`n8.1.3-34-ga35157abb9-20261108`, SHA256
`d9c6d414578b1d44c3b46a1922ed51e98325a4dbe51ef038e5985e17d0417ec5`,
matches GitHub's published asset digest. Select it with `--ffmpeg` or PATH.

## Verification and remaining work

- Seven Python transport tests cover a known independent CRC vector, arbitrary
  chunk sizes, packet loss/duplicates, adaptation-only continuity, pointer
  completion, discontinuity recovery and TOT/TDT CRC differences.
- Native replay/demux RTL test compares all 1802 DMA bytes at exact guest
  addresses under read/write stalls and hold cycles: 30 packets, eight sections,
  malformed CRC rejected, loss/duplicate recovery, full-ring rejection, wrap,
  high-halfword match routing, wrong-table rejection on the same PID, two
  independent channels sharing a PID and BE byte status semantics.
- An early real-firmware CPU/peripheral/DMA simulation reached 215M instructions,
  consumed 52 sections, made 1026 reads of section RAM and acknowledged all
  52 section interrupts, no CPU/model/GPU halt. This verifies delivery and guest
  consumption, not populated listings. That run preceded the routing correction
  below. A later 280M run reached native acquisition and programmed actual
  title/index filters; trace `native_mmio_prefilterfix_280M.log`, reconstructed
  `subscriptions_280M.json`. A fresh corrected run uses the title fixture.
- Three schedule tests cover actual boundary/offset behavior, overlap/provenance
  validation, aware timestamps and PID collisions.
- Real FFmpeg/FFprobe test generated a one-second local bars/tone stream,
  verified codec/resolution/rate, PMT/PCR/elementary PIDs and service ID, and
  decoded the whole result with no errors. `sim/media_end_to_end.log`.
- `pace_huffman.py` extracts the original tree from initialized operator RAM.
  Two Python tests cover all printable byte values and padding/phrase behavior.
  More decisively, `tb_huffman_native.sv` calls original function 800BECF0 on
  the actual FPGA CPU model: all four cases pass (empty string; leading/trailing
  spaces and (Stereo) phrase; punctuation/equals/digits; long text). This is
  independent guest-decoder validation, not just an encoder self-round-trip.
- The original ring-length helper800044BC runs on the FPGA CPU model with
  table_id in the last, penultimate and antepenultimate ring bytes. All three
  return701B for the circularly stored header. `sim/ring_native_test.log`.
- Transport-control RTL tests cover valid/empty/incomplete/non-sequential,
  maximum-size and oversized transfers, MMIO stalls and holding an accepted
  response across a download without repeating its side effect.
- SI tests verify private descriptor namespace/encoding, title record lengths,
  six-hour block selection, complete full-day coverage and every C1 reference.
- A reader test checks three exact188-byte file loops (a partial final DDR word)
  with DDR/byte stalls and hold. Configuration RAM tests clear all256 words,
  then restore the actual checkpoint routing/rules after reset.
- The registered-MMIO/circular-ring full-day simulation reaches300M instructions,
  delivers461 sections, makes11440 guest ring reads and acknowledges all461
  interrupts, without halt. It runs the title time-field callback24 times, but
  no Huffman/row rendering callback; the frame remains the original Guide menu.
  A later two-key Guide/Select run reaches310M,541 deliveries/acks, same display
  limitation. A no-transport keyboard control produces the original21 graphics
  completions, proving that the registered bus itself preserves that path.
  These precede the filter-RAM storage optimization; an updated native run is
  in progress with early Select and rotating C1 versions.

## Corrections found by native trace and Ghidra

The public reference's sixteen-unit interpretation was not adopted after
cross-checking actual guest writes. The checkpoint proves channel22 route word
96 selects bit10, whose pair5 low rule is73/FF; channel23 word97 selects bit5,
whose pair2 high rule is42/FF; channel24 word98 selects bit3, whose pair1 high
rule is40/FF. After acquisition channel21 word95 selects bit17, whose pair8
high rules are A3/FE, 0B/FF, B9/FE, CD/FF, 26/FF. These cannot be explained by
sixteen independently addressed units. They agree with the original boot
self-test's paired rule layout and source-channel routing at word8. The final
RTL implements 32 units, paired storage and per-PID routing; it does not accept
every section merely because no route was found.

The reference's pre-record ring wrapping was also corrected. Original helper
800044BC explicitly reads length bytes from the beginning when table_id is at
the inclusive ring end; it has a separate case for one length byte wrapping.
See `section_ring_length_native_decompile.txt` and the actual guest execution
test. Final DMA wraps every byte and publishes a modulo-ring producer pointer.
The original section task80004520 also confirms that the trailer's bit7 is a
CRC error indicator; a zero trailer denotes a valid record. It derives record
stride as section_length+4 and computes its hardware guard as consumer-32 with
circular wrap. `section_task_native_decompile.txt` records this independently
of the public reference.

Ghidra confirms native row parser800CB000 stores descriptor bytes2/3 and the
bitfields in byte4 at row offsets8/10/9/11, then calls the function pointer at
800CB2F8, which initialized RAM resolves to800BECF1 (MIPS16 Huffman decoder).
See `guide_row_native_parser_decompile.txt`.

Ghidra800BECF0 resolves two signed16-bit edge arrays through globals80120BE0/
80120BF0, count511 through80120BD0, and phrase pointers through80120C10. A
negative edge is complemented into a literal byte or phrase index. The first
byte carries a two-bit dictionary selector and six data bits. This exact ROM
tree has512 leaves; no downloaded public dictionary is required. Encoding uses
a minimum-bit phrase parse and pads with an internal-tree prefix, so no spurious
TAB, NUL or space is emitted. Original guest execution verifies final padding.

Ghidra 800C4C34 independently confirms C1's `(section_length-9)/9` record count,
the nine-byte wire to ten-byte guest record transformation, and alphabetical
and genre extension dispatch. `index_c1_native_parser_decompile.txt` records
the exact byte fields used by the fixture encoder. Programme-reference meaning
is cross-checked with the public reference and is still being tested in the
full guest; delivery alone is not treated as proof of a visible grid.

Remaining sequence: validate v048 timing and physical guest delivery; trace
title/index storage and application window/event consumers; then add measured
live ingress and actual MPEG2/MP2 decoder logic. The title/row encoder is
implemented and original-decoder tested. Obtain and attribute historical
schedule/media data separately.
Protected-loader cold boot remains its own unresolved RE task.

## Sources and RE evidence

- Original firmware driver, Ghidra output `re/demux_native_driver.txt`:
  `80004276` enable read, `8000427A` status, `80004284` W0C acknowledgement,
  `800042A6..800042C4` indirect pointer read/publication to guest RAM.
- Original firmware consumer helper, Ghidra `re/demux_native_consumer2.txt`,
  `80004ECC..80004F24`; actual native MMIO trace shows index `channel*4+2`
  updated with current consumer minus 32 bytes. Ring guard interpretation is
  a functional inference from those writes, covered by explicit boundary tests.
- Same-ROM public reference [GoRetroTv](https://github.com/ddunford/GoRetroTv),
  read-only checkout pinned at `fa3a471df9c273f4f62ecbcc6a566f3c6e871dd4`.
  Register/section/private descriptor facts cross-checked against the original
  guest and tests; its match-unit interpretation was corrected as above.
  Independent implementation here; GPL-2.0 source is not
  copied into this GPL-3.0-only RTL/tool implementation.
- [openTVtoXML](https://github.com/dave-p/openTVtoXML) is a DVB-S OpenTV to XMLTV
  **decoder**, not an XMLTV-to-OpenTV encoder. Its output still needs a native
  title encoder and a data source to feed this firmware.
- [TriHydera/sky-channels](https://github.com/TriHydera/sky-channels) supplies an
  England channel list in several formats; its README does not establish a
  1990-2020 historical schedule/lineup chronology.
- [Old Digibox music page](https://www.olddigibox.com/museum/epgs/background-music)
  exposes recordings by year via embedded players; no automatic archive API
  or source provenance was assumed. TVRDb's bot challenge and BBC Genome's 403
  prevented acquiring schedule data here. The other archive links remain
  research leads, not imported datasets.
- [FFmpeg build releases](https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases)
  supplied the isolated tools used by the end-to-end test. CLI help was used
  to verify muxer options against installed versions.

## Deployment addendum

v048 current compile: `compile_v048_transport_g.log` (seed 2), isolated sources
`builds/v048_transport`, demux source SHA256
`91f483e9f8d7036d8e395a2236609a3e9860519cf39ea449903d77f97c3d4a95`;
top source SHA256
`2946cbffaede0f611b4d26833fdf741d08a0988c719245fca146e620c5e9b533`.
Compile a was cancelled for the routing correction. A source-copy command for
compile b used the build directory twice; it was caught/cancelled immediately,
then the corrected source hash was checked in root and isolated build before c.
Compile c fit78%ALMs/70%RAM blocks but timing failed: -28.216ns through the
combinational modulo188 length check and about-13.8ns MMIO-to-CPU writeback.
Detailed paths are `output_files/transport_critical_paths.rpt`. It was not
deployed. These paths were redesigned as the counter and response register.
Compile d stopped at syntax checking; a missing space after a hex literal
caused `?` to be lexed as a numeric wildcard. A stale earlier protocol test
log was caught during that failure; final tests now propagate compile failure
before reporting results, and the corrected circular test passes freshly.
The original guest boundary helper and transfer/MMIO control tests also pass.
The final native simulation uses registered MMIO, circular writes, the full-day
index fixture and Select at 275M, targeting 300M. Evidence prefix:
`re/transport/native_final`; log `sim/guide_final_test.log`.
Compile e passed synthesis but failed routing congestion:80% nominal ALMs,
96% occupied LABs, heavy hold-delay routing. Its sources are archived in
`re/transport/rejected_sources_e`. Compile f moves the filter table into one
M10K; synthesis confirms8192 added RAM bits and registers fall42140->37332.
Earlier timing evidence is retained in `re/transport/timing_c_paths.rpt`.
Read-only Nucleus census of the final simulation finds236 named objects/41
created tasks; TASK30 is runnable. It does not prove an AV/device wait is the
cause of the missing redraw. `native_final_tasks.json` records the evidence.
Compile f completed and fitted at75% ALMs,387 RAM blocks,50 DSP blocks.
Core setup passes+1.066ns but the HDMI scaler misses setup by0.005ns; f was
not deployed. Its RBF and reports are preserved in `re/transport/build_f`.
Compile g retries placement with the same functional RTL and seed2.
The fresh early-key/versioned-index run consumes601 sections, acknowledges
all601 and renders ALL CHANNELS/no-signal. Primary Ghidra and RAM evidence
now points to the counted NVRAM/favourites rebuild as a lead for the temporary
UI wait. See `TRANSPORT_UI_FOLLOWUP.md`; its completion is not yet established.
Compilation/physical validation in progress; v047
remains the verified deployed fallback until a successful replacement test.
