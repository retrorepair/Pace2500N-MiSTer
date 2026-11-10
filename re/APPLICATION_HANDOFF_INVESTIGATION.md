# Valid-image selection and handoff investigation

8 November2026. Software research only; current FPGA is still v046 EXP.

## Resolved peripheral completion

The serial packet's second byte is a sequence field, not a read/write flag.
Initial guest requests are03011107,03024100,03035200. The opcode52 receive
callback06408 consumes no data and releases APeriph8000A6D0. Sending a framed
`02 <sequence> 52` reply through the genuine ISR, task, decoder and router lets
the waiting call return at9FC06312. Generic ACK10 leaves that call blocked:
`serial_sync_completion.json` versus `serial_sync_ack_only.json`. A fresh-reset
run confirms completion (`serial_completion_fresh_01.json`). Wrong sequence
also advances early requests, so sequence enforcement is not established.

SPI clock scheduling (64 instructions after request GPIO edge;8192 after RX
readiness), instantaneous console TX and the peripheral/timer clock ratios
remain hypotheses. These are not measured board timing.

Further original firmware requests11/41/51/12 are treated as output commands;
44 supplies two front-panel input bytes. FFFF is the ROM default and decodes
as no buttons. `test_front_panel.py` executes both the original receive handler
and button decoder. It also checks several pressed-bit controls.

## Firmware validation and output

Console output is captured from genuine UART writes:

```
1.2.7
01-1-45-0
02-1-45-0
03-0
```

Both original headers and payloads have zero CRC using the firmware algorithm.
`check_firmware_crc.py` verifies actual bytes. Optional `pace_crc_accel.py`
accelerates only the exact original loop/table and preserves its architectural
state, retirement and interrupt boundaries. `test_crc_acceleration.py` compares
against instruction stepping, including changed-code/table negative controls.
No CRC or image-validation result is forced.

`application_boot_03.json` reaches100M instructions, scheduler9FC0DE60, with
both valid flags800084B8/800084B4=1 and no observed application entry. Selected
header stored atA0002000:

```
4f420000 00000018 bfc20024 0017f62c
00000004 0000009f 0000002d 00000000
```

The bank aliases remain inferred and must not be treated as a documented
physical chip-select map.

## Current blocker

`application_handoff_ghidra.txt` and `boot_handoff_decompile.txt` show12614:
allocate32 stack bytes, copy32 bytes from the supplied header, release stack,
return. It contains no application jump.12610 is also an empty return.
The caller12846..12860 checks the nonzero selected entry, calls12614, copies
the header toA0002000, then calls036F8. That function configures an I2C device,
sleeps20 ticks, emits command12, then sleeps2 ticks repeatedly forever.

Static application startup exists atBFC2048C, reached by the stub atBFC2002C,
but is not reached by the observed loader path. Do not force its PC and call
that an authentic full boot. A separately labelled entry-point RE harness is
acceptable for studying downstream application requirements.

There is not yet evidence whether12614 is an intentional loader stub, missing
runtime overlay, altered dump, or part of an undocumented reset contract.
Older local v04/v042 ZIPs contain identical U202/U203 bytes. Original public
archives were located under phone-linked CrossDevice storage, but are offline
placeholders and could not be read. This was later resolved using the source
URL supplied by the user: http://colibri.bplaced.net/firmware.htm.

## Original publication verified

`re/original_archives/download_manifest.json` records URL, size and SHA256 for
fresh downloads of all three archives. Published full U202/U203 match the
project files exactly. Published131072-byte protected loader also matches
the first131072 bytes of U202 (SHA256
`e2d179258c149cc8455805179f24d314c1847d1fd25a9f30af91392707a31eb3`).
The published12614 bytes are unchanged. This rules out alteration introduced
by these project packages; it does not explain the missing handoff mechanism.

`info.txt` says the only dumper alteration was zeroing the four serial bytes.
The original JTAG manual's page2 board drawing names NEC D61032 and flash
AT49LV1614. Its text describes an external U1300 watchdog resetting the flash
and other ICs periodically. The exact SoC reset/boot-map contract remains
unknown; do not turn that note into an unsupported application-PC redirect.

## Decompressed application RE

`extract_application_ram.py` implements the actual20618..20764 startup copy
table and256-entry halfword dictionary decoder. The compressed section at
9FCD06F0 expands into800009F4. Original code outputs1029152 bytes (eight more
than the table's nominal length); extraction preserves that exact write count
and copy order. All five initialized segments match original MIPS execution:
`verify_application_extraction.py`, `application_extraction_comparison.json`.

Initialized-segment artifact SHA256:
`66273af550467e9baa87a178fa19ccbd533c9cf859263a90d152be461a0a86f8`.
Zero gaps are analysis placeholders, not a recovered runtime BSS image.
Ghidra project PaceAppRAM adds genuine cached/uncached flash and uninitialized
remaining RAM through PrepareApplicationProject.java.

`run_application_entry.py` explicitly starts atBFC2002C with empty RAM. It does
not claim the protected loader reaches it. Initial strict MMIO stops are
B0000012 (startup selector) andB0000010 (clock/tick selection). Subsequent
exploratory runs use explicit zero-MMIO policy. A byte output atB4080002 is
recorded without claiming its physical meaning. Original command53 builder
296F0 sends three distinct byte parameters; do not invent16-bit byte order for
the last two. `test_application_command53.py` executes the genuine builder.

An opt-in unknown-command transport-ACK control acknowledges packet receipt
without supplying identity, tuner, EEPROM or other device data. Reports record
each such request. Default unknown-command behavior still stops.18M-instruction
entry experiment runs the application's Nucleus scheduler with687 IRQs and265
EMMA timer acknowledgements; main task waits on FeSmInit801170B8, with FETask
waiting on an I2C completion semaphore80170288. No application video observed.

## I2C byte completion

Ghidra06BD4..06F54 identifies TX6040, status6010 mask04 (bit2), IRQ clear6050=0,
enable6060 bit0, START control9A and STOP99 onB2006000. Actual aggregator
mask200000 routes via CPUIP2. The guest ISR drives the entire byte sequence and
posts its completion semaphore. Candidate byte delay64 instructions is inferred.

`application_i2c_ack_01.json`: addressCA outputs3FFEA670 and completes via five
IRQ byte events. `application_i2c_nack_01.json`: no data is sent after the
address NACK, and original firmware returns the error path. This is a
write-only explicit profile, not a tuner/demodulator implementation. Other
addresses stop by default. An optional absent-device NACK control supplies no
read bytes. `application_i2c_ack_02.json` stops at address00; its partially
stopped I2C state should not be resumed (use ack_01 as clean predecessor).

`test_application_idle.py` compares100k normal/accelerated instructions,
including all GPR, CP0, RAM, timer/serial/I2C state, MMIO counts and IRQ events.
84168 idle instructions can be skipped with identical architectural results.

Read-only execution tracing: `python tools/trace_application_handoff.py`.
Ghidra project: `re/ghidra/PaceU202`; original firmware hashes unchanged.

## Latest strict frontend checkpoint

The address18/19 device uses LSI-style groups, not a flat incrementing register
array. Ghidra shows separate APR0/APR1 writes (`00 xx`, `01 xx`), group4
configuration writes, and a group5 program upload. General call00/06 matches
the LSI serial address initialization sequence. The available L64724 technical
manual (original LSI-authored document, local PDF/text/source metadata under
original_archives/) documents that interface and group7 reset read00.

**Exact derivative is not identified.** The native driver uploads1024 program
bytes and accesses group5 control atAPR0400. The releaseB L64724 manual documents
512 program bytes and controlAPR0208. Firmware also configures registers beyond
the L64724 map; saved L64734 datasheets provide a family comparison, not a full
register specification. Do not silently substitute one chip's control map.

`application_lsi_strict_02.json` stops honestly on that unsupported control:
15,351,668 instructions, PC80006E7E, group5 APR0400=D5. This is an emulator
capability boundary, not a firmware error. No CPU jump or completion result is
forced. `test_lsi_grouped.py` reruns from a clean predecessor, checks APR/readback
and uninitialized-read stops, verifies the guest's entire1024-byte upload against
actual application bytes800FC9B4..800FCDB3, and confirms the general call and
documented initial group7 read. Program SHA256:
`412837c684da392874a8d21e358d09baf51830e2bd6af915077abf8f18f1c094`.

Earlier seed00/seedFF experiments with a **provisional flat register file** both
reachedB4080000 board-input read at16,265,787 instructions. Their matching control
flow shows initial07 value alone does not determine that path. Their register
semantics do not match the grouped device; do not present them as validated
frontend emulation or port them to FPGA. Strict grouped profile supersedes them.

Fresh Atmel-profile loader run61M still selects both valid images and waits,
with no app entry. Executed cache operations seen in that snapshot are early
index-tag invalidation/fill operations8/9/20 and one TagLo=0 write, not an
observed store-instruction-data patch of12614. The loader handoff remains a
separate unresolved issue. Current FPGA and fallback archives remain intact.


## Functional frontend, UART and native graphics completion (14:49 UTC)

A separate optional LsiObserved512Device profile accepts the actual512-word
program/control layout, models shared documented reset/counter behavior and
records control D5/D7. It remains functional no-RF: no acquisition instruction
execution, no silicon-ID byte and no satellite lock. The strict mismatch stop
is preserved separately. No flat register seeds are used in the new runs.

Ghidra8002E2C0 identifies B4080000..7 as an external16550 UART with address
XOR3 byte lanes. This corrects earlier descriptions as a board input/output.
Native initialization sets divisor4 and LCR3; the model supplies an empty RX
FIFO, instantaneous TX and no modem/carrier response. UART IRQ is not modelled.

The firmware constructs a60-byte GPU solid-fill418F0000 packet. DMA12's
40-byte descriptor pointer is B0009100; descriptor word3 is source, word8 is
inclusive end, word5=0014003C. GPU control603C bit10 enables DMA. Status6040
bit0 is busy, not ready. Native DMA ISR80005E28 reads halfword9122 and9142,
clears busy state, invokes registered callback and acknowledges9130/9150.
The original IRQ table800FC69C maps logical DMA IRQ2 to mask00000002 and
callback80005E29. An initial mask4 experiment wrongly entered GPIO ISR and
is superseded by application_graphics_03.

The new graphics profile accepts only this observed packet and derives all
coordinates, color and RAM destinations from the guest. Original code completed
and acknowledged4/4 commands, filling luma00575798..005A8198 with10 and
chroma005A81A8..005C16A8 with80. These are black/neutral video initialization,
not Guide output. DMA timing is immediate and not cycle accurate.

At34M instructions with the absent EEPROM control, the firmware continually
retries A0. Ghidra1101C performs the readiness-poll retry; 06C4A..06C64 builds
two big-endian address bytes. Native adapter294B8 selects that two-byte mode.
An opt-in BlankEeprom16 starts FF and persists only actual guest writes in an
assumed64KiB address space. No original EEPROM image is available; page wrap
and write-cycle timing are unmodelled. Snapshot application_eeprom_02 shows
16,435 byte reads and51 byte writes through the original I2C ISR. The firmware
read a16KiB block, then began initializing structures at1800 onwards and
reading them back. A0 pointer writes are recorded across repeated START to A1.

All of this is software application-entry experimentation. The protected
loader handoff remains unresolved and FPGA v046 EXP is unchanged. Flash
contains genuine Guide text/resources and EPG3.0.11 version information, but
no Guide rendering has been observed. Tests and results are recorded in
validation_20261108_graphics.json.


## Later application and indexed graphics (18:46 UTC)

Native serial TX completion atB2002000 now runs6 genuine IRQ10000/ISR2CCA0
acknowledgements for queued600001110474, clearing the transmit count and
releasing STXD0. No external serial receive bytes are provided. An additional
B4080100..7 byte region is classified as MMIO; it remains under the explicitly
unsafe zero-read experiment, not a validated external chip implementation.

Application EEPROM initialization proceeds normally, through20,201 reads and
3,816 guest-written bytes by185M instructions. MIPS32 unaligned merge operations
pass36 Ghidra p-code cases. A new exact guarded application CRC accelerator
preserves real data-dependent results, GPRs, counters and retired counts.
Its deadline logic includes one-shot timer boundaries even when IRQs masked;
100003-instruction differentials with masked pending/periodic tests pass.
The first conservative long replay skipped0 instructions because pending
masked IRQs inhibited it; it matches the normal trace through185132885.

At185132885, the first new GPU packet is01AC0000. Original builder086FC and
rectangle API1FCA0 duplicate a byte color into the color halves, supply two
field pointers and full-frame coordinates. Surface583FE8 has720x576 geometry,
two720x288 byte allocations at584048/5B6A58 and a256-entry16-bit palette at
5E9468. Four consecutive commands cover y0,144,288,432, height144, colorDC.
The inferred interlaced index8 fill now writes both buffers within their actual
allocations. Native DMA completion matches8/8. Palette API1FA30 explicitly
uses YUV bytes and neutral80/70 handling. Exact scanout/palette conversion
still requires validation; no Guide rendering is claimed.

A separate graphics capture-only diagnostic acknowledged unimplemented packets
without pixel execution. Its pixels are invalid and it is NOT an output proof.
That initial capture accidentally completed the faulting DMA twice by replaying
before reexecuting its unretired write; this is superseded by indexfill_01.
CLI now rejects --complete-pending-graphics after an unsupported-opcode stop;
resume that faulting instruction normally. The option remains valid for older
snapshots stopped later in a poll with an already-retired DMA start.

Strict no-RF profile stops on derivative group3 APR001C. An explicitly labelled
--lsi-extended-status-zero control supplies zeros only for APR24..33, matching
the original driver's accepted derivative address range; silicon reset values
remain unconfirmed, and chipID6 remains unsupported. Under that control the
frontend polling finishes. Snapshot indexfill_02 at210M has main TASK0 and GUI
TASK30 in their event queues and no further graphics work. Both index buffers
contain onlyDC, not text or a Guide screen.

Original RX handler2AA80 decodes peripheral opcode02 and key dispatcher2A810
uses key table800FCEC0. Synthetic user input is injected through framed serial
RX with GPIO-ready/IRQ flow, never through guest RAM edits. GuideCC maps to
native0600 and Sky80 maps to0108. Contributor LIRC Navigator recording agrees
(complemented low-byte33 for Guide). Guide press/release was decoded toCC
at801073B6 in guide_key_01, but no new graphics resulted. Sky key continuation
and another Guide press are being traced. Still no Guide output or new FPGA
release. Hardware remains v046 EXP with v044 fallback intact.


## 19:30 UTC: Guide diagnostic output

See GUIDE_DIAGNOSTIC_CHECKPOINT.md for the successful two-RAM-word experiment,
actual guest-pixel Guide category menu and All Channels search dialog, exact
patch provenance, MIPS32 J/JAL delay-slot IRQ correction, packed graphics copy
and repeatable checkpoints. This supersedes earlier no-Guide software findings;
it does not solve the protected-loader handoff or establish MiSTer boot.
