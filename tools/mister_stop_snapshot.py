#!/usr/bin/env python3
"""Read-only (runs on MiSTer): wait for the frontend to lock (state 7) and then
leave it, and save the 16 MB guest RAM at that instant to the given file."""
import mmap, os, sys, time
out = sys.argv[1]
limit = float(sys.argv[2]) if len(sys.argv) > 2 else 120
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
ram = mmap.mmap(fd, 0x1000000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x30000000)
w = lambda a: int.from_bytes(ram[a & 0xffffff:(a & 0xffffff) + 4], 'big')
t0 = time.time(); locked = None
while time.time() - t0 < limit:
    state = w(0x800fcdc4)
    if locked is None and state == 7:
        locked = time.time(); print(f'locked at {locked-t0:.2f}s', flush=True)
    if locked is not None and (state != 7 or w(0x800fcdbc) == 5):
        blob = ram[:]
        print(f'left state 7 after {time.time()-locked:.2f}s (state {state})', flush=True)
        open(out, 'wb').write(blob)
        break
    time.sleep(0.002)
else:
    print('timeout')
