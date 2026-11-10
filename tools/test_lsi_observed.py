"""Functional no-RF derivative must never invent silicon ID or lock."""
from pace_lsi_grouped import LsiObserved512Device
from pace_probe import StopProbe
p=LsiObserved512Device();p.select(1);p.write(4);p.select(0);p.write(0)
p.select(5);p.write(0xd7);assert p.micro_enabled and p.control==0xd7
p.select(7);p.write(0);assert not p.micro_enabled
p.status[0]=12;p.status[1]=34;p.select(0);p.write(1);p.select(1);p.write(0)
p.select(3);p.write(0xff);assert p.status[0]==p.status[1]==0
p.select(0);p.write(55);p.select(4);p.write(0x8f);p.apr=55;assert p.peek()==0x8c
p.select(2);p.apr=0;assert [p.read() for _ in range(4)]==[0,0,0,0]
p.select(3);p.apr=6
try:p.read()
except StopProbe:pass
else:raise AssertionError('Invented chip identity')
assert not p.report()['satellite_lock'] and not p.report()['microcontroller_executed']
print('PASS: observed derivative controls, counter-pair clear, self-clearing reset, no RF lock and unknown ID rejection')
