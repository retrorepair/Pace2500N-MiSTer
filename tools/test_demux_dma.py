"""Configured DMA from relocated RAM; test gating, CRC and bounds behavior."""
from pathlib import Path
from pace_probe_demux import DemuxProbe
from pace_probe import StopProbe
flash=Path('firmware/FLASH_U202.bin').read_bytes()
fixture=flash[0x1b188:0x1b188+1128]

def configured(data=fixture,enable=1,limit=0x1000):
    p=DemuxProbe(flash,unsafe_zero_mmio=True)
    def indexed(port,index,value):
        p.write(0xb000a000+port+4,value);p.write(0xb000a000+port,0xc000|index)
    p.ram[0x20000:0x20000+len(data)]=data
    words=[0,0,0,0x20000,0,0,0,0,0x20000+len(data)-1,0]
    p.ram[0x40000:0x40028]=b''.join(x.to_bytes(4,'big') for x in words)
    for n,v in enumerate((0,0,limit,0x1fff,0x2000,0,0x3000,0x3fff)):indexed(0x124,n,v)
    for index,value in ((0,0x00ff00ff),(16,0x00ff00ff),(32,0x00ff01ff),(0x80,enable),(0x81,2)):
        indexed(0x144,index,value)
    p.write(0xb000a014,0x14000);p.write(0xb000a018,0x14001)
    p.write(0xb000a120,0xa0020050)
    p.write(0xb000a000,0xe00)
    p.write(0xb0009090,0x40000)
    assert p.read(0xb0009120)==0
    return p
def start(p):p.write(0xb0009010,0x20)
p=configured();start(p)
assert p.read(0xb0009120)==0x20
assert p.ram[0x500000:0x5000b8]==flash[0x1b77c:0x1b834]
assert p.ram[0x502000:0x5020b4]==flash[0x1b834:0x1b8e8]
assert p.crc_dropped==2 and len(p.demux_outputs)==3
assert p.demux_banks[0x124][0]==184 and p.demux_banks[0x124][4]==0x20b4
p=configured(enable=0);start(p)
assert p.ram[0x500000:0x5000b8]==bytes(184) and p.demux_banks[0x124][0]==0
assert p.ram[0x502000:0x5020b4]==flash[0x1b834:0x1b8e8]
changed_filter=configured()
changed_filter.write(0xb000a148,0x00ff02ff)
changed_filter.write(0xb000a144,0xc020)
start(changed_filter)
assert changed_filter.ram[0x500000:0x5000b8]==bytes(184)
assert changed_filter.ram[0x502000:0x5020b4]==flash[0x1b834:0x1b8e8]
corrupt=bytearray(fixture);corrupt[188+30]^=1
p=configured(corrupt);start(p)
assert p.crc_dropped==3 and p.ram[0x502000:0x5020b4]==bytes(180)
assert p.ram[0x500000:0x5000b8]==flash[0x1b77c:0x1b834]
wrong_pid=bytearray(fixture)
for n in (0,2,4):wrong_pid[n*188+2]=2
p=configured(wrong_pid);start(p)
assert p.ram[0x500000:0x5000b8]==bytes(184)
p=configured(limit=16)
try:start(p)
except StopProbe as e:assert 'ring full' in str(e)
else:raise AssertionError('Output bounds not enforced')
print('PASS: relocated descriptor/input/output, PID/filter gating, CRC rejection, real pointer counts and ring bounds')
