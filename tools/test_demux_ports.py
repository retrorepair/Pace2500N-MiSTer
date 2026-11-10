"""Run genuine U202 indexed-port helper instructions against the model."""
from pathlib import Path
from pace_probe_demux import DemuxProbe

p=DemuxProbe(Path('firmware/FLASH_U202.bin').read_bytes(),unsafe_zero_mmio=True)
def call(pc,index,value=None):
    p.pc=pc;p.mode16=True;p.r[4]=index;p.r[31]=0xbfc00001
    if value is not None:p.r[5]=value
    for _ in range(100):
        p.step16()
        if p.pc==0xbfc00000:return p.r[2]
    raise AssertionError('Genuine indexed helper failed to return')
call(0xbfc0b41c,0x80,0x11223344)
call(0xbfc0b41c,0x11,0x89abcdef)
assert call(0xbfc0b3f4,0x80)==0x11223344
assert call(0xbfc0b3f4,0x11)==0x89abcdef
call(0xbfc0b3c0,3,0x1fffff)
assert call(0xbfc0b38c,3)==0x1fffff
assert call(0xbfc0b38c,4)==0
print('PASS: genuine U202 filter and buffer indexed-port helpers write/read distinct entries')
