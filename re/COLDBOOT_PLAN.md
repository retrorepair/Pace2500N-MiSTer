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
3. Application start-up peripherals: B2001013/33/43, the external 16550 UART (B4080000), demux
   registers B000A004/094/128/148, the LSI front end's start-up (microprogram upload, status), and
   each read override the simulator profile declares - modelled where evidence allows, otherwise
   carried as a commented approximation.
4. Hardware: build, MGL with only FLASH + EEPROM save + live ring, telemetry, then the Guide and
   the A/V selection gate measured on the box.
