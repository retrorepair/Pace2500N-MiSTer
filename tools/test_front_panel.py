"""Execute the genuine digital-input reply handler and button decoder."""
from pathlib import Path
from pace_probe_boot_peripheral import BootPeripheralProbe
p=BootPeripheralProbe(Path('firmware/FLASH_U202.bin').read_bytes(),unsafe_zero_mmio=True)
def until_return():
    for _ in range(200):
        p.step16()
        if p.pc==0xbfc00000:return p.r[2]
    raise AssertionError('Guest input routine did not return')
p.ram[0x2000:0x2005]=bytes([4,7,0x44,0xff,0xbf])
p.pc=0xbfc06614;p.mode16=True;p.r[4]=0x80002000;p.r[31]=0xbfc00001
until_return();assert p.ram[0x825c:0x825e]==bytes.fromhex('ffbf')
for raw,expected in (('ffff',0),('feff',8),('ffbf',0x10),('ffdf',0x80),('fffb',0x200),('ff7f',0x40),('ffef',0x100)):
    p.ram[0x2000:0x2002]=bytes.fromhex(raw)
    p.ram[0x1000:0x1004]=bytes(4);p.ram[0x100c:0x1010]=(0xbfc00001).to_bytes(4,'big')
    p.r[16]=0x80002000;p.r[29]=0x80001000;p.r[3]=0;p.pc=0xbfc06576;p.mode16=True
    assert until_return()==expected,(raw,p.r[2],expected)
print('PASS: genuine reply44 storage and active-low front-panel decode; FF FF means no buttons')
