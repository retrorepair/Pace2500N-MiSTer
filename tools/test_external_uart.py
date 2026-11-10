from pace_external_uart import ExternalUart
u=ExternalUart();u.write(0,0x83);u.write(3,12);u.write(2,0)
assert u.read(3)==12 and u.read(2)==0 and u.divisor==[12,0]
u.write(0,3);u.write(3,65);assert u.tx==b'A'
assert u.read(6)==0x60 and u.read(1)==1 and u.read(5)==0
u.rx.extend(b'B');assert u.read(6)==0x61 and u.read(3)==66 and u.read(6)==0x60
u.rx.extend(b'C');u.write(1,0x87);assert not u.rx and u.read(1)==1
print('PASS: external UART byte lanes, DLAB divisor isolation, FIFO reset, RX/TX state')
