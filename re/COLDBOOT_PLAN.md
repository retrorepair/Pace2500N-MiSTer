# Cold boot from flash (branch `cold-boot`)

Goal: the core boots the firmware from its reset vector as a powered-on 2500N does, instead of
resuming the diagnostic checkpoint (RAM.bin/STATE.bin). Then the firmware reads its own EEPROM at
start-up (bookings, favourites, PIN, settings) and nothing in RAM is host-made.

## Facts this rests on

- The loader -> application handoff is a warm reset requested with front-panel command `0x12`;
  RAM keeps the loader's signature and header across it and the second boot jumps to the
  application (`re/APPLICATION_HANDOFF_INVESTIGATION.md`, top section; proven in the Python
  simulator by `tools/run_warm_reset_handoff.py`).
- From that handoff the application starts up in the Python simulator with no RAM edits, reads and
  formats a blank EEPROM, and idles; the old checkpoint's "root ready" edit is not needed. Its A/V
  selection gate waits for a selected service, which needs the transport/MPEG path the FPGA has
  (`tools/run_application_after_handoff.py`).
- `re/COLDBOOT_MMIO_INVENTORY.md` (`tools/coldboot_mmio_inventory.py`): every device register the
  loader (power-on and after the reset) and the application start-up touch, against what the FPGA
  implements.

## Stages

1. Core plumbing (done, untested on hardware): OSD "Boot: Cold from flash" (status bit 7); guest
   RAM cleared after power-on (SDRAM keeps nothing); hold only for the flash (and the EEPROM save
   file); CPU starts at BFC00000 (no checkpoint); peripheral registers reset to zero instead of the
   checkpoint's values (the simulator's declared unknown-register policy); the front-panel
   controller resets the CPU and the chip's own blocks (`soc_reset`) on command 0x12, never the
   external RAM, EEPROM, loaded files or incoming stream. System simulation: `sim/vl/tb_sys.sv +cold`.
2. Loader peripherals, against the simulator's models: front-panel replies (0x52 completion, 0x44
   buttons: already in RTL), the boot FIFO at B00020B0/B8, the demux self-test (DMA channel 5 and
   match-word readback), NOR flash ID mode, I2C device 0xCA (already ACKed).
   - Demux self-test (done in RTL, system simulation): `rtl/pace_transport_dma.sv` models DMA
     channel 5 (B0009090 descriptor, B0009010 bit 5 start, B0009120 bit 5 complete) feeding the
     demux's transport input between packets. The demux now uses the ring layout the guest
     programs instead of the application's constants: B000A120 low half = RAM page (application
     0x7A, loader 0x3B), indirect field 0 = start/write pointer, 2 = limit, 3 = inclusive end
     (application dump: channel*0x3000 / +0x2FE0 / +0x2FFF). Each record's trailer byte is the
     matching filter number (U202's expected buffers at 1B834 end with 01; the application reads
     only bit 7). Delivery no longer depends on the interrupt enables (the loader never writes
     B000A0D8 and polls). B000A144/148 rule read-back is served with a busy bit. In `+cold` the
     two pointers reach 0xB8 and 0x20B4, as the loader requires.
   - Boot data port (done): B00020B4 mode 1/2, B00020B0 words read back in order (64 deep; the
     test uses 60). The first self-test (BFC0AEF4) reads back all 240 words.
   - Result (`tb_sys +cold`, 18 Nov 2026): with both self-tests passing the boot flag 800081F8
     clears and BOOTMain takes the normal path: board latch B4180000, GPIO, front-panel link
     (commands 11, 41, 52, 51, 10, then 0x44 button polls up to frame 0x1F, as in the Python
     run), the application image CRC (BFC129E4), then `03 20 12 00` at 5.3 s. The front-panel
     reset restarts the CPU with RAM kept and the second boot jumps to the application at
     BFC2048C at 7.6 s.
   - NOR flash identify (done): rtl/pace_r4k.sv decodes the JEDEC unlock/autoselect/reset
     commands in the 1F800000 window per chip and returns the identify codes. The loader
     identifies U202 twice per boot (16-bit writes at 1F80AAAA/1F805554). Codes: AT49LV1614
     001F/00C0 (the 2500N board drawing; the loader's table also lists MBM29LV160B 0004/2249).
     Program/erase remain unmodelled (dropped, counted as unmapped).
3. Application start-up peripherals: B2001013/33/43, the external 16550 UART (B4080000), demux
   registers B000A004/094/128/148, the LSI front end's start-up (microprogram upload, status), and
   each read override the simulator profile declares - modelled where evidence allows, otherwise
   carried as a commented approximation.
4. Hardware: build, MGL with only FLASH + EEPROM save + live ring, telemetry, then the Guide and
   the A/V selection gate measured on the box.
