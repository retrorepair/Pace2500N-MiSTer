"""Interrupt a J/JAL delay slot, ERET, and verify branch restart and link state."""
from pathlib import Path
from pace_probe_timed import TimedProbe
for opcode in (2,3):
    p=TimedProbe(Path('firmware/FLASH_U202.bin').read_bytes(),counter_ticks=1)
    p.pc=0x80002000;p.cp0={9:0,11:1,12:0x10008001,13:0};p.timer_armed=True
    p.ram[0x2000:0x2008]=((opcode<<26)|0xc00).to_bytes(4,'big')+bytes(4)
    p.ram[0x180:0x184]=(0x42000018).to_bytes(4,'big')
    p.run(1)
    assert p.pc==0x80000180 and p.cp0[14]==0x80002000
    assert p.cp0[13]&0x80000000 and p.delay_origin is None
    if opcode==3:assert p.r[31]==0x80002008
    p.timer_armed=False;p.cp0[13]&=~0x8000
    p.run(2)
    assert p.pc==0x80002000 and not p.cp0[12]&2
    p.run(4)
    assert p.pc==0x80003000 and p.branch is None
    if opcode==3:assert p.r[31]==0x80002008
print('PASS: J and JAL delay-slot IRQ saves branch EPC/BD, ERET restarts branch and preserves link')
