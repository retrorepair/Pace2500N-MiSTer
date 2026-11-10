"""Guard the separation between diagnostic patches and original ROMs."""
from pathlib import Path
from hashlib import sha256
from pace_probe_native_serial import NativeSerialProbe
from pace_diagnostic_gates import apply_diagnostic_sky_gates, apply_diagnostic_root_ready, ORIGINAL_U202

original=Path('firmware/FLASH_U202.bin').read_bytes()
p=NativeSerialProbe(original);p.entrypoint_experiment=True
p.ram[0x54f84:0x54f88]=b'\xff'*4
apply_diagnostic_sky_gates(p,native_only=True)
assert p.ram[0x54f84:0x54f88]==bytes(4)
assert p.flash==p.nor[0].data==original
assert len(p.diagnostic_firmware_patches)==1
apply_diagnostic_sky_gates(p)
assert p.flash[0x72fa1]==p.nor[0].data[0x72fa1]==0x76
assert len(p.diagnostic_firmware_patches)==2
assert sum(a!=b for a,b in zip(p.flash,original))==1
apply_diagnostic_sky_gates(p)
assert len(p.diagnostic_firmware_patches)==2
assert sha256(Path('firmware/FLASH_U202.bin').read_bytes()).hexdigest()==ORIGINAL_U202
q=NativeSerialProbe(original);q.entrypoint_experiment=True
try:apply_diagnostic_sky_gates(q)
except AssertionError:pass
else:raise AssertionError('Uninitialized RAM accepted')
assert q.flash==original and q.ram[0x54f84:0x54f88]==bytes(4)
q.ram[0x54f84:0x54f88]=b'\xff'*4
apply_diagnostic_sky_gates(q,native_only=True)
q.ram[0x105e9c:0x105ea0]=(0x80200000).to_bytes(4,'big')
q.ram[0x2000c4:0x2000c8]=(0x80300000).to_bytes(4,'big')
apply_diagnostic_root_ready(q)
assert q.ram[0x300014:0x300018]==b'\0\0\0\1'
assert len(q.diagnostic_firmware_patches)==2 and q.flash==q.nor[0].data==original
print('PASS: staged patch provenance, alias consistency, idempotence, precondition refusal and untouched original ROM')
