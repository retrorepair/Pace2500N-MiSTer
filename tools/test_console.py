from pathlib import Path
from pace_probe_console import ConsoleProbe
p=ConsoleProbe(Path('firmware/FLASH_U202.bin').read_bytes(),unsafe_zero_mmio=True)
p.write(0xb2001030,0x80);p.write(0xb2001000,0x35);p.write(0xb2001010,0)
assert not p.uart_tx and p.uart_divisor==[0x35,0]
p.write(0xb2001030,3)
p.pc=0xbfc028ec;p.mode16=True;p.r[4]=0x41;p.r[31]=0xbfc00001
for _ in range(100):
    p.step16()
    if p.pc==0xbfc00000:break
else:raise AssertionError('Genuine UART putc helper did not return')
assert p.uart_tx==b'A' and p.read(0xb2001050)==0x60
p.uart_rx.extend(b'B');assert p.read(0xb2001053,1)==0x61
assert p.read(0xb2001003,1)==ord('B') and p.read(0xb2001050)==0x60
print('PASS: genuine UART putc, DLAB divisor isolation, BE byte lanes and RX-ready status')
