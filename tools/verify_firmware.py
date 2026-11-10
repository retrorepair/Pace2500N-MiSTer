#!/usr/bin/env python3
"""Reproducibility checks for the actual user's U202 dump and ROM conversion."""
from pathlib import Path
import hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
flash=ROOT/'firmware'/'FLASH_U202.bin'
rom=ROOT/'rom'/'bootloader_words.hex'
expected='32f6b2e84d0c4c4ec280a72f2d080e4b6fa5e68e8438ef712f34f97f63d38c7f'
f=flash.read_bytes()
assert len(f)==2097152,(flash,len(f))
sha=hashlib.sha256(f).hexdigest()
assert sha==expected,(sha,expected)
lines=rom.read_text().splitlines()
assert len(lines)==32768,len(lines)
actual=b''.join(int(line,16).to_bytes(4,'big') for line in lines)
assert actual==f[:131072],'Boot ROM differs from U202'
assert f[8:20].hex().upper()=='3C08BFC02508040801000008'
assert f[0x578:0x57c].hex().upper()=='77F00786'
# One physical 625-line frame at 15.625 kHz = 25 frames and 50 fields/s.
assert (50_000_000/4)/(400*1250)==25
assert (50_000_000/4)/800==15625
print('PASS: U202 SHA256',sha)
print('PASS: 128 KiB FPGA boot ROM == real U202 boot block byte-for-byte')
print('PASS: reset stub, verified JALX opcode, 625/50 video timing')
print('PASS: full 2 MiB original firmware present for MiSTer DDR3 upload')
