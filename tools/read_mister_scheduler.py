"""Read this Pace core's reserved DDR scheduler state on MiSTer; no writes."""
import mmap
import os
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
try:
    with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x30008000) as ram:
        print('Kernel tick 8000842C:',ram[0x42c:0x430].hex())
        print('Ready queues 800083D0 / 800083FC:',ram[0x3d0:0x3d4].hex(),ram[0x3fc:0x400].hex())
    with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x30013000) as ram:
        print('BOOTMain TCB 80013AE0:',ram[0xae0:0xb58].hex())
finally:
    os.close(fd)
