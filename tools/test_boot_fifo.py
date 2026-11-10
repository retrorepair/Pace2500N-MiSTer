from pace_probe_boot_fifo import BootFifoProbe
p=BootFifoProbe(bytes(2097152),unsafe_zero_mmio=True)
p.write(0xb00020b4,1)
for value in (0xaaaaaaaa,0x55555555,0xffffffff,0):p.write(0xb00020b0,value)
p.write(0xb00020bc,0x80);p.write(0xb00020b4,2)
assert [p.read(0xb00020b0) for _ in range(4)]==[0xaaaaaaaa,0x55555555,0xffffffff,0]
assert p.fifo_reads==p.fifo_writes==4
assert not p.flag_writes
print('PASS: data-port patterns retained in order; no boot-flag writes')
