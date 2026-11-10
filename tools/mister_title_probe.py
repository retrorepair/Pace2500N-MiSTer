#!/usr/bin/env python3
"""Read-only: report whether the firmware has decoded synthetic title text into guest RAM."""
import mmap, os, sys, time
mins = int(sys.argv[1]) if len(sys.argv) > 1 else 5
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
ram = mmap.mmap(fd, 0x1000000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x30000000)
for m in range(mins):
    blob = ram[:]
    found = {s: blob.find(s.encode()) for s in ('LOCAL TEST ONE', 'LOCAL TEST TWO', 'TEST ONE 13:00', 'TEST TWO 20:00')}
    print(time.strftime('%H:%M:%S'), {k: hex(v) if v >= 0 else '-' for k, v in found.items()}, flush=True)
    if m + 1 < mins:
        time.sleep(60)
