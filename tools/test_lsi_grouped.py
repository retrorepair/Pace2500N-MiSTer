"""Check grouped addressing and real guest upload up to variant mismatch."""
from pathlib import Path
import gzip,pickle,json,hashlib
from pace_lsi_grouped import LsiGroupedDevice
from pace_probe_application_i2c import ApplicationI2CProbe
from pace_probe import StopProbe

d=LsiGroupedDevice();d.select(7);assert d.read()==0
d.select(0);d.write(0x34);d.select(1);d.write(2);assert d.apr==0x234
d.select(4);d.write(0x78);d.write(0x56);assert d.apr==0x236
d.select(0);d.write(0x34);d.select(4);assert d.read()==0x78 and d.read()==0x56
try:d.read()
except StopProbe:pass
else:raise AssertionError('Uninitialized configuration reads must stop')

with gzip.open('re/application_i2c_ack_01.pkl.gz','rb') as f:old=pickle.load(f)
p=ApplicationI2CProbe(old.flash);p.__dict__.update(old.__dict__)
p.i2c_ack_18=True;p.i2c_nack_unknown=True;p.lsi_grouped=LsiGroupedDevice();p.fast_idle=True
p.run(17000000)
assert p.status.startswith('LSI variant control at group5 APR0400=D5'),p.status
raw=bytes(p.lsi_grouped.groups[5][n] for n in range(1024))
image=Path('re/application_initialized_segments.bin').read_bytes()
assert raw==image[0xfc9b4:0xfcdb4]
assert p.lsi_grouped.general_calls==[6]
assert p.lsi_grouped.variant_mismatch==dict(group=5,apr='0400',value='D5')
assert p.i2c_reads[0]['register']=='group7' and p.i2c_reads[0]['value']=='00'
assert not p.device18_seeds and not p.device18_registers
stem='re/application_lsi_strict_02'
Path(stem+'.json').write_text(json.dumps(p.report(),indent=2)+'\n')
with gzip.open(stem+'.pkl.gz','wb') as f:pickle.dump(p,f)
print('PASS: grouped APR/readback, uninitialized-read stop; genuine1024-byte upload SHA256',hashlib.sha256(raw).hexdigest(),'; unsupported control stops')
