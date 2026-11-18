import mmap, os, sys
# Compare the flash image the core keeps in DDR (0x32000000) with FLASH_U202.bin and report the
# byte shift if it is displaced.
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
f = mmap.mmap(fd, 0x200100, mmap.MAP_SHARED, mmap.PROT_READ, offset=0x32000000)
fl = open('/media/fat/games/Pace2500N/FLASH_U202.bin', 'rb').read()
bad = sum(1 for a in range(0, 0x200000, 8) if f[a:a+8] != fl[a:a+8])
print('%s: qwords differing %d of %d' % (sys.argv[1] if len(sys.argv) > 1 else '', bad, 0x200000 // 8))
if bad:
    probe = fl[0x1000:0x1040]
    for shift in range(-64, 65, 2):
        if f[0x1000 + shift:0x1040 + shift] == probe:
            print('  image found shifted by %+d bytes' % shift)
    print('  DDR 0x00..0x20:', f[0:0x20].hex())
