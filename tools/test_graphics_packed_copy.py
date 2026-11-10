"""Exercise odd-start interlace, packed source pitch, overlap and bounds refusal."""
from pathlib import Path
from pace_probe_graphics import GraphicsProbe
from pace_probe import StopProbe
p=GraphicsProbe(Path('firmware/FLASH_U202.bin').read_bytes())
def command(source=0x1000):
    w=[0]*15;w[0]=0x00ac0000;w[1]=source;w[5]=0x8042f354
    w[7]=0x2000;w[8]=0x3000;w[11]=7;w[12]=1<<16|2;w[13]=3<<16|2
    w[14]=0xdeadbeef # unused, must not become a colour
    return b''.join(v.to_bytes(4,'big') for v in w)
p.ram[0x1000:0x100c]=bytes(range(1,13));p.ram[0x2000:0x3100]=b'\xa5'*0x1100
p.graphics_command(command())
for row in range(4):
    line=row+1;dest=[0x2000,0x3000][line&1]+(line//2)*8+2
    assert p.ram[dest:dest+3]==bytes(range(row*3+1,row*3+4))
    assert p.ram[dest-1]==p.ram[dest+3]==0xa5
# Source overlaps destination: all source rows must be sampled before writing.
p.ram[0x2000:0x200c]=bytes(range(41,53));p.graphics_command(command(0x2000))
for row in range(4):
    line=row+1;dest=[0x2000,0x3000][line&1]+(line//2)*8+2
    assert p.ram[dest:dest+3]==bytes(range(41+row*3,44+row*3))
before=bytes(p.ram)
try:p.graphics_command(command(len(p.ram)-4))
except StopProbe:pass
else:raise AssertionError('Out-of-bounds source accepted')
assert p.ram==before
print('PASS: packed copy pitch, odd-start field order, padding, unused color, overlap and bounds')
