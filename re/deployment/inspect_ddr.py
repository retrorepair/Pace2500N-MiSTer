import mmap,os,collections,json
from pathlib import Path
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
with mmap.mmap(fd,2097152,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x22000000) as m: actual=m[:]
expected=Path('/media/fat/games/Pace2500N/FLASH_U202.bin').read_bytes()
Path('/tmp/pace_ddr_flash.bin').write_bytes(actual)
wrong=[n for n,(a,b) in enumerate(zip(actual,expected)) if a!=b]
print('Expected first 64:',expected[:64].hex())
print('DDR first 64:',actual[:64].hex())
print('Mismatch count:',len(wrong),'first offsets:',[hex(n) for n in wrong[:32]])
print('Mismatch byte lanes:',dict(collections.Counter(n%8 for n in wrong)))
for start in (0x100,0x10000,0x20000,0x100000,0x1ffff0): print(hex(start),actual[start:start+16].hex(),expected[start:start+16].hex())
with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x20008000) as m: print('RAM 8200 pointers:',m[0x200:0x208].hex())
os.close(fd)
