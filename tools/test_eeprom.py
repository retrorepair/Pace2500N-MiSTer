"""Check address phases, erased data, STOP commit and read-back isolation."""
from pace_eeprom import BlankEeprom16
p=BlankEeprom16();p.begin(0xa0);p.write(0x12);p.write(0xff)
p.begin(0xa1);assert [p.read(),p.read()]==[255,255]
p.begin(0xa0)
for n in (0x12,0xff,0x37,0x49):p.write(n)
assert p.data[0x12ff:0x1301]==b'\xff\xff'
p.stop();assert p.data[0x12ff:0x1301]==bytes.fromhex('3749')
p.begin(0xa0);p.write(0x12);p.write(0xff);p.begin(0xa1)
assert [p.read(),p.read(),p.read()]==[0x37,0x49,255]
assert p.write_count==2 and p.data[0x12fe]==255
print('PASS: EEPROM16 address setup/repeated START, erased reads, STOP commit and isolated guest write/readback')
