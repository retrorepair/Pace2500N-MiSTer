# Both original hardware self-tests pass in fresh software execution

This supersedes the earlier second-test failure in BOOT_FLAG_AND_TRANSPORT_SELFTEST.md.
The FPGA remains v046 EXP; none of this new demux/NOR/serial behavior is in RTL.
No application or Sky Guide boot is observed.

## Fresh result

Command: `python tools/run_demux_probe.py --out re/demux_fresh_04`

The original U202 is unchanged (SHA25632f6b2e84d0c4c4ec280a72f2d080e4b6fa5e68e8438ef712f34f97f63d38c7f).
Both BFC0AEF4 and BFC0AFDC return0. BFC004FC itself writes0 to800081F8 at
instruction3212289. BOOTMain reaches9FC012E6 at3562835, takes the normal path,
initializes GPIO byte80013CCC to1 and proceeds into flash identification.
Six million instructions reach scheduler idle without unsupported instructions.

This is a fresh reset-to-boot run, not just a resumed snapshot. It does not
supply the earlier constant B0009120 ready override. DMA completion status is
derived from the descriptor transfer. RAM, flags and guest PC are not forced.
Other unknown MMIO still explicitly returns zero; these remain research models.

## Guest-configured DMA and section filtering

The genuine firmware programs descriptor00007D60:

- source1FC1B188, inclusive end1FC1B77B (1524 bytes from original flash);
- later the same descriptor references1FC1B8F8 for a32-byte flush transfer.

Ghidra BFC0B38C/BFC0B3C0 identify buffer indexed-port command/data at
B000A124/A128; BFC0B3F4/BFC0B41C identify filter portsA144/A148. Bit15 selects
writes and bit14 is polled busy. The model handles these transactions, rather
than returning expected counts directly.

The captured guest configuration gives:

- filter enable maps at indices80=1 and81=2;
- paired value/mask entries000=00FF00FF,010=00FF00FF,020=00FF01FF;
- PID descriptors atA014=00014000 andA018=00014001;
- output address configurationA120=A001003B;
- buffer write pointers0=0 and4=2000, bounds2=1000 and6=3000.

The inferred filter interpretation compares section byte0 then bytes3..9,
skipping section_length. Low16 bits describe filter0, high16 filter1. The model
uses guest PID enables/masks, CRC, output pointer/bounds and address config.
It produces these actual RAM writes:

| PID | Output | Destination | Bytes |
| --- | --- | --- | --- |
| 1 | 1 | 003B2000 | 180 |
| 0 | 0 | 003B0000 | 36 |
| 0 | 0 | 003B0024 | 148 |

Two bad-CRC sections are dropped. Updated pointers naturally becomeB8 and20B4.
The genuine code's two poll loops finish; BFC0B194 compares all46 and45 words
against its expected buffers, and returns success. The model contains no
expected buffer data or ROM fixture offsets; source bytes come from the DMA
descriptor. Destination addresses likewise come from guest configuration.

Mapping semantics are inferred from this driver/test. Full filter capacity,
mode bits, descriptor chains, IRQs, ring wrapping, CRC options and cycle timing
are not implemented/verified. Output trailer/filter association is supported
by the self-test, not a complete NEC programming specification.

## Further normal-path initialization

BFC0373C/BFC0378C write a software-shadowed byte latch atB4180000. The model
records these output writes; reads remain unsupported, with no invented external
effects. This permits the real GPIO initializer BFC03910 to run.

BFC02810 performs NOR unlock/autoselect/reset atBF800000: writesAA atAAAA,
55 at5554,90 atAAAA, reads manufacturer/device and writesF0. The explicitly
inferred MBM29LV160B profile uses0004/2249 from U202's own supported-device table
at1ADC8. The firmware accepts it and returns to read-array mode. Actual board
chip ID is unmeasured. BF800000/BFA00000 plus cached aliases map to the two
supplied2MiB images; this mapping is inferred. Boot alias instruction reads
remain array reads (CPU cache behavior is approximate). Erase/program stop.

## Tests

- test_demux_ports.py executes genuine U202 helpers for distinct indexed reads/writes.
- test_demux_dma.py relocates descriptor, RAM input and output buffers, reproduces
  expected data, disables filters, changes PIDs, corrupts a CRC and tests ring bounds.
- test_boot_fifo.py checks data-port order and no flag writes.
- test_emma_timer.py checks timer/IRQ gates and acknowledgement.
- test_nor.py checks unlock/ID/reset and rejects unsupported writes.
- test_serial_peer.py checks provisional serial clock/IRQ/escape capture and stopping.

All pass. Fresh full-run evidence is demux_fresh_04.json and its RAM/pickle
snapshot; demux_configured_snapshot.json captures original guest registers.

## Current next blocker: peripheral serial response

After GPIO and NOR initialization, BOOTMain again waits for APeriph8000A6D0.
Now the channel is initialized: it no longer fails the earlier GPIO gate.

Ghidra serial ISR BFC053E8 tests B2009020 bit0, reads RX fromB2009010, clears
bit0 and activates a deferred handler. EMMA interrupt bit2000 is enabled.
The serial task BFC05424 decodes ESC1B escaping and00 frame termination.

An exploratory peer assumes GPIO0 falling requests a byte transfer. It supplies
idle RX00 only, raises the genuine serial IRQ and lets RTOS tasks transmit.
Captured decoded requests are03011107 and03024100. Wire bytes:
`00 03 01 11 07 00 00 03 02 41 1B 00 00`.
The task's GPIO/serial actions and framing support the hypothesis, but no real
board capture confirms the clock relationship or external-device identity.

The model deliberately stops at captured requests: it has not fabricated a
reply. Next RE is the genuine reply-dispatch/command semantics for03024100,
including what values may be obtained from known board/device state.
Do not conflate these later peripheral exchanges with the now-passed demux test.

Command: `python tools/capture_serial_request.py --requests 2`;
evidence serial_peer_capture_02.json. Snapshot inputs are local
trusted probe artifacts. Hardware core remains unchanged.
