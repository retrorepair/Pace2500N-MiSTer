"""Architected timer/interrupt tests; counter rate is deliberately synthetic."""
from pace_probe_timed import TimedProbe

def probe(code='00000000',mode=False,status=0x8001):
    image=bytearray(2097152);image[0x100:0x100+len(code)//2]=bytes.fromhex(code)
    p=TimedProbe(bytes(image),counter_ticks=1);p.pc=0xbfc00100;p.mode16=mode
    p.cp0.update({9:0,11:1,12:status,13:0});p.timer_armed=True
    return p
p=probe();p.run(1)
assert p.interrupt_count==1 and p.pc==0x80000180 and p.cp0[14]==0xbfc00104 and p.cp0[12]&2
p=probe(status=0x408001);p.run(1);assert p.pc==0xbfc00380
p=probe(mode=True,code='6a00');p.run(1)
assert p.cp0[14]==0xbfc00103 and not p.mode16
p=probe(code='1000000300000000');p.run(1)
assert p.cp0[14]==0xbfc00100 and p.cp0[13]&0x80000000 and p.branch is None
p=probe(status=0);p.run(1)
assert p.interrupt_count==0 and p.cp0[13]&0x8000
p=probe(code='40825800');p.r[2]=100;p.cp0[13]=0x8000;p.run(1)
assert p.interrupt_count==0 and not(p.cp0[13]&0x8000) and p.cp0[11]==100
p=probe(code='40826800',status=0);p.r[2]=0xffffffff;p.cp0[13]=0x8000;p.run(1)
assert p.cp0[13]==0x8300
p=probe(status=6);p.run(1);assert p.interrupt_count==0
print('PASS: Count/Compare, acknowledgement, IRQ masks/vectors, EPC ISA and branch-delay origin')
