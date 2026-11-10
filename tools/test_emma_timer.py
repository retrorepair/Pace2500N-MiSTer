from pace_probe_emma_timer import EmmaTimerProbe
p=EmmaTimerProbe(bytes(2097152),unsafe_zero_mmio=True,peripheral_ticks=4)
p.write(0xb000d050,100)
p.write(0xb000d020,1);p.write(0xb000d0c0,1);p.write(0xb000d030,1)
p.advance_counter(24);assert not p.timer_pending
p.advance_counter(1);assert p.timer_pending and not p.cp0[13]&0x400
p.write(0xb0000040,0x40);assert p.cp0[13]&0x400
assert p.read(0xb0000030)==0x40 and p.read(0xb000d0d0)==1
p.write(0xb000d0e0,1);assert not p.cp0[13]&0x400 and p.acknowledgements==1
p.advance_counter(25);assert p.timer_pending and p.expirations==2
p.write(0xb000d0c0,0);assert not p.cp0[13]&0x400
p.write(0xb000d030,0);n=p.expirations;p.advance_counter(1000);assert p.expirations==n
print('PASS: inferred timer enable, reload, periodic expiry, local/global IRQ gates and W1C ack')
