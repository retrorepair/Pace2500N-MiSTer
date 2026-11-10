"""Differentially compare application idle fast-forward with CPU stepping."""
import gzip,pickle,copy
from pace_probe_application_i2c import ApplicationI2CProbe
with gzip.open('re/application_i2c_ack_01.pkl.gz','rb') as f:old=pickle.load(f)
a=ApplicationI2CProbe(old.flash);a.__dict__.update(old.__dict__)
b=copy.deepcopy(a);a.fast_idle=False;b.fast_idle=True
limit=a.steps+100000
a.run(limit);b.run(limit)
for key in ('steps','pc','mode16','branch','delay_origin','r','cp0','ram','timer_regs','timer_remaining','timer_pending','expirations','acknowledgements','interrupt_count','interrupt_events','mmio','serial_regs','gpio_regs','rx_wire','clock_due','i2c_regs','i2c_due','i2c_events','peer_requests','replies','device18_registers','device18_pointer','i2c_payload_index','i2c_receive','i2c_rx_valid','i2c_reads'):
    assert getattr(a,key)==getattr(b,key),key
assert b.idle_skipped>a.idle_skipped
print('PASS:100k instructions, all GPR/CP0/RAM, timer/serial/I2C state and IRQ events agree; skipped',b.idle_skipped-a.idle_skipped)
