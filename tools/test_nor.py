from pace_nor import NorBank
from pace_probe import StopProbe
b=NorBank(bytes(range(256))*8192)
assert b.read(0,4)==0x00010203
for address,value in ((0xaaaa,0xaa),(0x5554,0x55),(0xaaaa,0x90)):b.write(address,value,2)
assert b.read(0,2)==4 and b.read(2,2)==0x2249
b.write(0,0xf0,2);assert b.read(0,4)==0x00010203
try:b.write(0x1234,0x5678,2)
except StopProbe:pass
else:raise AssertionError('Unsupported flash write accepted')
print('PASS: NOR unlock/autoselect/reset, BE array reads and unsupported-write diagnostic')
