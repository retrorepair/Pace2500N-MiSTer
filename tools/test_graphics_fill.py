"""Check relocated/strided solid fills and reject unsupported commands."""
from pathlib import Path
from pace_probe_graphics import GraphicsProbe
from pace_probe import StopProbe
p=GraphicsProbe(Path('firmware/FLASH_U202.bin').read_bytes())
p.ram[0x1000:0x1050]=bytes([0xaa])*0x50
w=[0]*15;w[0]=0x418f0000;w[7]=0x1000;w[11]=7;w[12]=0x10002;w[13]=0x20003;w[14]=0x12340000
def command():return b''.join(n.to_bytes(4,'big') for n in w)
p.graphics_command(command())
expected=bytearray([0xaa]*0x50)
for off in (0x14,0x24,0x34):expected[off:off+8]=bytes.fromhex('1234')*4
assert p.ram[0x1000:0x1050]==expected
assert p.graphics_events[-1]['width']==4 and p.graphics_events[-1]['height']==3
w[0]=0
try:p.graphics_command(command())
except StopProbe:pass
else:raise AssertionError('Unknown opcode accepted')
w[0]=0x418f0000;w[11]=1
try:p.graphics_command(command())
except StopProbe:pass
else:raise AssertionError('Row overrun accepted')
print('PASS: relocated solid fill, x/y and row stride, preserved padding; unknown opcode/overrun rejected')
