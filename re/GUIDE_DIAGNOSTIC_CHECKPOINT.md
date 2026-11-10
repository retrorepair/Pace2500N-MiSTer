# Actual firmware Guide output — 8 November 2026, 19:30 UTC

The original Pace application now draws its complete ten-item TV GUIDE menu
in our software CPU/peripheral probe. Select opens ALL CHANNELS and the native
"Searching for listings / Please wait" dialog. No menu strings, glyphs or
images are inserted by the host. All displayed content is CPU-rasterized into
guest scratch RAM and copied by guest-submitted DMA12 graphics packets.

**This is a diagnostic application-entry experiment, not a completed MiSTer
boot. Two host RAM interventions are essential in the demonstrated run. The
protected-loader handoff is still unresolved. There is no channel/schedule
input, RF lock or populated listings grid.** FPGA v046 EXP and v044 fallback
have not been changed or redeployed by this continuation.

## Output and provenance

- `application_guide_diagnostic_200M.png`: full TV GUIDE category menu,
  720x576, 28 palette indices, 23 DMA completions and 23 native ISR acks.
  PNG SHA256 `ff9db48735894079378720e29d85b56a85185ed9586d0f68c07175e166d26537`.
- `application_all_channels_diagnostic_210M.png`: ALL CHANNELS searching
  dialog, 15 palette indices, 44 completions/44 acks.
  PNG SHA256 `ed3583f2741d61ea09e4c3137383ab64d2abd279953eb5acd3b7058185463c1a`.
- Each PNG has a `.png.json` sidecar with frame hashes, actual display-list
  addresses and the exact host interventions. These are software RAM exports,
  not photographs or SSH captures of the FPGA.
- Root register B0004200 = 01583FE8, descriptor 00583FE8, indexed fields
  00584048/005B6A58, CLUT 005E9468. Packed CLUT Y6/Cb4/Cr4 conversion is inferred
  from native packer 80008C30 and corroborating public RE; hardware scanout and
  exact analogue colour have not been verified.

## Reference and independent checks

Dan Dunford's public same-ROM emulator, GoRetroTv, was discovered this session:
https://github.com/ddunford/GoRetroTv
Pinned revision `fa3a471df9c273f4f62ecbcc6a566f3c6e871dd4`, GPL-2.0.
Read-only local clone: `reference_goretrotv`. Its firmware manifest matches
both of our original U202/U203 SHA256 values exactly. Its chronological RE
notes contain corrections; later findings supersede earlier key/IRQ guesses.

The public notes explicitly disclose a manual loader handoff and presentation
interventions. We have not treated that emulator as proof of a solved boot.
Our own Ghidra run independently confirms:

- `80054DDC` returns pool word `80054F84` (initially FFFFFFFF) unless AV-state
  byte 80161D3C is nonzero and 80161D40 differs from 8010161C.
- `80085128` sets a window root at `windowArray + 100*id + 60`, recursively
  attaches/detaches the tree and updates its drawing/window context.
- Actual unpatched snapshot at184M has window1 root zero. Applying the native
  default-return diagnostic before its first call preserves root80430A14.

Ghidra reports: `application_presentation_gate_ghidra.txt`,
`application_presentation_gate_decompile.txt`,
`application_window_binding_ghidra.txt`,
`application_window_binding_decompile.txt`.

## Two RAM interventions in the successful experiment

1. At143268918 instructions, before the first call to80054DDC, change the
   default-return literal at80054F84: FFFFFFFF ->00000000.
2. At184000000, after subsequent ROM CRC validation, change the existing,
   already-bound root object's readiness word80430A28 (=root80430A14+14):
   00000000 ->00000001. Root address is resolved from the live window table,
   not assumed by the CLI. This is host-forced application state, not a
   modeled peripheral reply.

This is the reference's earlier two-RAM-word diagnostic. The successful run's
U202 bytes and NOR alias both remain identical to the original ROM. A separate
optional alternative experiment changes Ocode initializer byte9FC72FA1
75->76; applying that initializer after it already executed did not update
the existing root and did not draw the menu. Those flash-patched snapshots
(`application_diagnostic_gates_01..04`, `application_guide_diagnostic_01`)
are not the successful output proof.

Both RAM interventions are recorded in reports with `firmware_modified=true`.
Original ROM files have not been modified. `pace_diagnostic_gates.py` checks
original SHA256, alias consistency and preconditions. These controls stay
opt-in. They must not become undocumented default hardware responses.

## Graphics and CPU fixes

The new00AC0000 opcode is an indexed packed-source copy. Actual first packet
uses source0055C288, packed592x112 bytes, destination x128,y0 in two720-pixel
field buffers. Unused words2..6 are stack values. Subsequent packet is packed
720x144 to x0,y112; menu rows are independent copies of newly rasterized
scratch content. Code accepts only the observed packed-source profile and
rejects a complete source descriptor until separately implemented.

All source rows are sampled before destination writes; interlaced destination
uses field=line&1, row=line>>1. Unit checks cover odd-start fields, padding,
packed pitch, overlap, unused colour word and bounds refusal. No unsupported
packet was acknowledged without pixel execution in the successful run.

An interrupt occurring after a MIPS32 J/JAL instruction exposed a CPU bug:
the deferred delay slot was not tagged as such, so EPC named the slot with
BD clear. ERET then fell through into unrelated code. `TimedProbe.run` now
includes opcodes2/3 in delay-slot tracking. Regression interrupts both J and
JAL, checks branch EPC/BD, executes ERET and verifies branch restart/link.
Replaying from the pre-copy snapshot then advances past the previous fault,
has no exception-console output and completes the menu. No CPU PC/ISA was
manually corrected in the successful continuation.

Application CRC acceleration now handles both NOR aliases, respecting ID
mode, bank bounds and peripheral/IRQ deadlines. Twelve differential cases
(three sources, four deadline profiles) compare100003 normal/accelerated
instructions, all registers/RAM/CP0/timer/IRQ state and instruction visits.

## Reproduce/resume

All commands run from the Pace2500N project directory with tools on Python's
script import path. CPython works; standalone PyPy is faster. Output limits
are absolute instruction totals. Use `--compact-history` to avoid huge JSON.

Start from the unmodified120M application snapshot:

```text
python tools/run_application_entry.py --snapshot re/application_serial0_02.pkl.gz --fast-crc --lsi-extended-status-zero --stop-before-pc 80054DDC --steps 190000000 --compact-history --out re/application_first_gate_checkpoint
python tools/run_application_entry.py --snapshot re/application_first_gate_checkpoint.pkl.gz --diagnostic-sky-native-only --steps 184000000 --compact-history --out re/application_native_gate_01
python tools/run_application_entry.py --snapshot re/application_native_gate_01.pkl.gz --diagnostic-sky-root-ready --remote-key CC --steps 205000000 --compact-history --out re/application_guide_ramgates_01
```

With current graphics code the last command continues instead of stopping on
00AC0000. The saved187991806 pre-copy snapshot remains useful for replay.
The actual successful current checkpoints are:

- `application_guide_fault_trace` at190M: fixed delay-slot replay, frame/tab
  bar, no exception. Historical filename reflects the investigation, not a
  fault in this final snapshot.
- `application_guide_ramgates_03` at200M: Guide category menu after a second
  CC press from190M.
- `application_all_channels_01` at210M: Select5C from200M. LIRC records
  SELECT as inverted A3; native key path is the ordinary serial RX route.

```text
python tools/run_application_entry.py --snapshot re/application_guide_ramgates_03.pkl.gz --remote-key 5C --steps 210000000 --compact-history --out re/NEW_NAME
python tools/render_guest_osd.py re/NEW_NAME.pkl.gz re/NEW_NAME.png
```

The renderer refuses snapshots with capture-only unexecuted graphics.
Other already-declared approximations remain: empty-RAM manual app entry,
synthetic instruction timing, immediate DMA completion, blank diagnostic
EEPROM, transport-only ACKs, unsafe-zero unknown MMIO and unconfirmed
extended LSI status zeros. No satellite lock or listings data was fabricated.

## Validation and next work

`validation_20261108_guide.json` records eight passing checks: CRC,
J/JAL delay-slot IRQ, solid fill, interlaced fill, packed copy, native graphics
ISR, diagnostic patch guards and application idle differential.

The next functional gap for listings is delivery/acquisition of DVB SI data
through the actual demux ring/interrupt path. The public reference supplies
useful driver-derived facts (corrected +D8 enable/+B8 status, channel index
pointer reads and ring layout), but those must be checked against our ROM and
implemented as explicit inputs. For a genuine boot, still trace the protected
loader's missing handoff and replace presentation-state interventions with
the firmware's real AV/SI preconditions. Hardware needs its own implementation
and SSH screenshot verification; these software pictures do not establish it.
