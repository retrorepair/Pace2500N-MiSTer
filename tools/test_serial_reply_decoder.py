from pathlib import Path
from pace_probe_demux import DemuxProbe
from pace_probe_serial_ack import encode_frame
p=DemuxProbe(Path('firmware/FLASH_U202.bin').read_bytes(),unsafe_zero_mmio=True)
def validate(body,length=None):
    p.ram[0x2000:0x2000+len(body)]=body
    p.pc=0xbfc05738;p.mode16=True;p.r[4]=0x80002000;p.r[5]=len(body) if length is None else length;p.r[31]=0xbfc00001
    for _ in range(100):
        p.step16()
        if p.pc==0xbfc00000:return p.r[2]
    raise AssertionError('Guest decoder did not return')
assert validate(bytes([2,7,0x10]))==1
assert validate(bytes([3,7,0x10]))==0
assert validate(bytes([1,7]))==0
assert validate(bytes([31])+bytes(31))==0
assert encode_frame(bytes([2,0,0x1b]))==bytes([2,0x1b,0,0x1b,0x1b,0])
print('PASS: genuine U202 message-length validation and escaped reply encoding')
