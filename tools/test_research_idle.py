"""Fast idle must preserve architectural state across a real timer interrupt."""
from pathlib import Path
from pace_probe_timed import TimedProbe
flash=Path('firmware/FLASH_U202.bin').read_bytes()
probes=[]
for fast in (False,True):
    p=TimedProbe(flash,fast_idle=fast,counter_ticks=8)
    p.pc=0x9fc0de4c;p.mode16=False
    p.r[1]=0x80010000;p.r[9]=1000000
    p.cp0.update({9:100,11:50000,12:0x8001,13:0})
    p.timer_armed=True
    p.ram[0x180:0x188]=bytes.fromhex('4089580042000018')
    p.run(100000)
    probes.append(p)
a,b=probes
assert a.status==b.status and a.pc==b.pc and a.r==b.r and a.cp0==b.cp0
assert a.ram==b.ram and a.branch==b.branch and a.delay_origin==b.delay_origin
assert a.interrupt_events==b.interrupt_events and a.interrupt_count==b.interrupt_count==1
assert a.steps==b.steps==100000 and a.idle_skipped==0 and b.idle_skipped>90000
print('PASS: idle acceleration preserves all GPR/CP0/RAM/PC, delay state and IRQ event')
