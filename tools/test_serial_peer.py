from pace_probe_serial_peer import SerialPeerProbe
from pace_probe import StopProbe
p=SerialPeerProbe(bytes(2097152),unsafe_zero_mmio=True)
p.write(0xb0000040,0x2000);p.write(0xb2009000,0x80);p.write(0xb2009030,1)
wire=[3,2,0x41,0x1b,0,0x1b,0x1b,0]
for n,byte in enumerate(wire):
    p.write(0xb2009010,byte)
    p.write(0xb200a000,1);p.write(0xb200a000,0)
    p.steps+=64
    try:p.advance_counter(0)
    except StopProbe:
        assert n==len(wire)-1;break
    assert p.read(0xb2009020)&1 and p.cp0[13]&0x400
    assert p.read(0xb0000030)&0x2000 and p.read(0xb2009010)==0
    p.write(0xb2009020,0)
    assert not p.cp0[13]&0x400
else:raise AssertionError('No stop at unknown peripheral response')
assert p.peer_requests==['030241001b']
assert not p.flag_writes and p.serial_rx==0
print('PASS: provisional GPIO clock, serial IRQ gating/ack and escaped frame capture; unknown response stops')
