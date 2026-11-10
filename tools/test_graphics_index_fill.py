"""Check full-frame rectangle mapping into separately padded field buffers."""
from pathlib import Path
from pace_probe_graphics import GraphicsProbe
p=GraphicsProbe(Path('firmware/FLASH_U202.bin').read_bytes());p.ram[0x1000:0x2100]=b'\xa5'*0x1100
w=[0]*15;w[0]=0x01ac0000;w[1]=w[7]=0x1000;w[2]=w[8]=0x2000
w[11]=7;w[12]=(1<<16)|2;w[13]=(3<<16)|2;w[14]=0x120034
p.graphics_command(b''.join(v.to_bytes(4,'big') for v in w))
for line in range(1,5):
    base=0x1000 if line%2==0 else 0x2000;start=base+line//2*8+2
    assert p.ram[start:start+3]==bytes([0x12 if line%2==0 else 0x34])*3
    assert p.ram[start-1]==p.ram[start+3]==0xa5
assert p.ram[0x1000:0x1008]==b'\xa5'*8
print('PASS: indexed rectangle with odd starting line, independent field colors and untouched padding/rows')
