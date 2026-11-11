#!/usr/bin/env python3
"""Make rom/bootloader_words.hex (the core's boot ROM) from your own U202 flash dump.

The core boots from the genuine first 128 KiB of the box's U202 flash, held in
FPGA block RAM (rtl/pace_bootrom.sv: 32768 big-endian 32-bit words). That image
is part of the original firmware, so it is never distributed: build it here from
your own dump, then compile the core.

Usage: python tools/make_bootrom.py [firmware/FLASH_U202.bin]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
flash = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'firmware' / 'FLASH_U202.bin'
data = flash.read_bytes()
if len(data) != 2 << 20:
    sys.exit(f'{flash}: {len(data)} bytes; a U202 dump is 2 MiB')
out = ROOT / 'rom' / 'bootloader_words.hex'
out.write_bytes(b''.join(data[i:i + 4].hex().upper().encode() + b'\n' for i in range(0, 128 << 10, 4)))
print(f'wrote {out} (128 KiB boot block of {flash.name})')
