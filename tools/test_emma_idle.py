"""External timer idle skipping must preserve all architectural state/events."""
from pathlib import Path
from pace_probe_emma_timer import EmmaTimerProbe
probes=[]
for fast in (False,True):
    p=EmmaTimerProbe(Path('firmware/FLASH_U202.bin').read_bytes(),unsafe_zero_mmio=True,
                     counter_ticks=8,peripheral_ticks=4,fast_idle=fast)
    p.pc=0x9fc0de4c;p.mode16=False;p.r[1]=0x80010000
    p.cp0.update({9:0,11:0x7fffffff,12:0x401,13:0})
    # IRQ handler acknowledges the real model, then ERET resumes the loop.
    p.timer_armed=True
    p.ram[0x180:0x194]=bytes.fromhex('3c1ab000375ad0e0241b0001af5b000042000018')
    for a,v in ((0xb000d050,4096),(0xb000d020,1),(0xb000d0c0,1),(0xb0000040,0x40),(0xb000d030,1)):p.write(a,v)
    p.run(100000);probes.append(p)
a,b=probes
assert a.pc==b.pc and a.r==b.r and a.cp0==b.cp0 and a.ram==b.ram
assert a.branch==b.branch and a.delay_origin==b.delay_origin
assert a.interrupt_events==b.interrupt_events and a.acknowledgements==b.acknowledgements>90
assert b.idle_skipped>80000 and a.idle_skipped==0
print('PASS: external-timer idle acceleration preserves all GPR/CP0/RAM/PC and IRQ events')
