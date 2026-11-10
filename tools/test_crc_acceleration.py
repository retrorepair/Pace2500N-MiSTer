"""Differential check against ordinary execution, including timer IRQs."""
from pathlib import Path
import random
from pace_probe_boot_peripheral import BootPeripheralProbe
from pace_probe import StopProbe
class TestProbe(BootPeripheralProbe):
    def step16(self):
        if self.pc==0xbfc00000:raise StopProbe('returned')
        return super().step16()
flash=Path('firmware/FLASH_U202.bin').read_bytes();rng=random.Random(2500)
for length in (0,1,7,32,127,4096):
    data=bytes(rng.randrange(256) for _ in range(length));initial=rng.getrandbits(32);probes=[]
    for fast in (False,True):
        p=TestProbe(flash,unsafe_zero_mmio=True,counter_ticks=8,peripheral_ticks=4,fast_crc=fast)
        p.pc=0x9fc129e4;p.mode16=True;p.r[4]=initial;p.r[5]=0x80002000;p.r[6]=length;p.r[31]=0xbfc00001
        p.ram[0x2000:0x2000+length]=data
        p.cp0.update({9:0,11:0x7fffffff,12:0x401,13:0});p.timer_armed=True
        p.ram[0x180:0x194]=bytes.fromhex('3c1ab000375ad0e0241b0001af5b000042000018')
        for a,v in ((0xb000d050,30000),(0xb000d020,1),(0xb000d0c0,1),(0xb0000040,0x40),(0xb000d030,1)):p.write(a,v)
        p.run(100000);probes.append(p)
    a,b=probes
    assert a.status==b.status=='returned' and a.pc==b.pc and a.r==b.r and a.cp0==b.cp0 and a.ram==b.ram,length
    assert a.steps==b.steps and a.interrupt_events==b.interrupt_events and a.delay_origin==b.delay_origin,length
    if length>=7:assert b.crc_skipped_instructions>0
assert probes[1].interrupt_count>0
for address in (0xbfc20000,0xbf820000):
    pair=[]
    for fast in (False,True):
        p=TestProbe(flash,unsafe_zero_mmio=True,fast_crc=fast)
        p.pc=0x9fc129e4;p.mode16=True;p.r[5]=address;p.r[6]=32;p.r[31]=0xbfc00001
        p.run(1000);pair.append(p)
        assert p.status=='returned' and p.r[2]==0
    assert pair[0].r==pair[1].r and pair[0].steps==pair[1].steps
changed=bytearray(flash);changed[0x129e4]^=1
assert not TestProbe(bytes(changed),fast_crc=True).crc_guard
changed=bytearray(flash);changed[0x1bae4]^=1
assert not TestProbe(bytes(changed),fast_crc=True).crc_guard
print('PASS: exact CRC state/retirement/IRQs, RAM and2 ROM aliases; modified code/table disables shortcut')
