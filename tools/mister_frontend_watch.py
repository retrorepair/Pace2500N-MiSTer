#!/usr/bin/env python3
"""Read-only once-a-second timeline of the firmware's frontend/lock state on MiSTer.

Guest RAM is at HPS DDR 0x30000000 (big-endian). No writes are made.
  800FCDC4 frontend acquisition state, 80105C00 acquired flag,
  800FCDBC/C0 frontend command mailbox (pending/last),
  80105B68 lock byte (status 5 when set), 80105B6C/70 search state words.
"""
import mmap, os, sys, time
secs = int(sys.argv[1]) if len(sys.argv) > 1 else 120
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
ram = mmap.mmap(fd, 0x200000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x30000000)
w = lambda a: int.from_bytes(ram[a & 0x1fffff:(a & 0x1fffff) + 4], 'big')
last = None
t0 = time.time()
while time.time() - t0 < secs:
    row = (w(0x800fcdc4), w(0x80105c00), ram[0x105b68], ram[0x105b69], w(0x80105b6c), w(0x80105b70), w(0x800fcdbc), w(0x800fcdc0))
    if row != last:
        print(f'{time.time()-t0:6.1f}s state={row[0]} acquired={row[1]} lock={row[2]} b69={row[3]} '
              f'search={row[4]:08x} {row[5]:08x} cmd={row[6]:08x} last_cmd={row[7]:08x}', flush=True)
        last = row
    time.sleep(0.05)
