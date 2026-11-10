#!/usr/bin/env python3
"""Read-only check of this core's reserved DDR flash against uploaded U202.

Run on MiSTer after the Pace full-flash MGL has loaded. No memory is written.
Linux /dev/mem read() rejects this reserved range; mmap() may support it.
"""
import hashlib
import mmap
import os
from pathlib import Path

expected=hashlib.sha256(Path('/media/fat/games/Pace2500N/FLASH_U202.bin').read_bytes()).hexdigest()
assert expected=='32f6b2e84d0c4c4ec280a72f2d080e4b6fa5e68e8438ef712f34f97f63d38c7f','U202 file is not the verified original'
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
try:
    with mmap.mmap(fd,2097152,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x32000000) as region:
        actual=hashlib.sha256(region).hexdigest()
    print('U202 file SHA256:',expected)
    print('DDR flash SHA256:',actual)
    if actual!=expected:
        raise SystemExit('FAIL: reserved DDR flash differs from U202')
    with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x30008000) as region:
        print('Guest RAM 80008200:',region[0x200:0x208].hex())
    print('PASS: all 2 MiB of DDR flash match genuine uploaded U202')
finally:
    os.close(fd)
