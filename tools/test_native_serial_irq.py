"""The genuine serial ISR must release the pending transmit semaphore."""
import gzip,pickle
from pace_probe_native_serial import NativeSerialProbe
old=pickle.load(gzip.open('re/application_guide_attempt_01.pkl.gz','rb'))
p=NativeSerialProbe(old.flash);p.__dict__.update(old.__dict__)
buffer=int.from_bytes(p.ram[0x1c2b1c:0x1c2b20],'big')&0x1fffffff
length=int.from_bytes(p.ram[0x1c2b20:0x1c2b24],'big')
expected=bytes(p.ram[buffer:buffer+length])
p.serial0_enabled=True;p.attach_pending_serial0();p.run(p.steps+10000)
assert p.status=='step limit',p.status
assert p.serial0_completions==length and p.serial0_acks==length
assert p.serial0_due is None and not p.serial0_regs[0xb2002070]&2
assert p.serial0_tx==expected and not p.serial0_regs[0xb2002060]
assert int.from_bytes(p.ram[0x1c2b20:0x1c2b24],'big')==0 # guest TX remaining at context+58
print('PASS: native EMMA IRQ10000/ISR2CCA0 sends actual queued bytes',expected.hex(),'and clears guest transmit count; no RX supplied')
