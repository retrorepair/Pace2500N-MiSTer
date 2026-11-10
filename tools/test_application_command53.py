"""Execute the original RAM command builder, and check packet-only ACK policy."""
from pathlib import Path
from pace_probe_application import ApplicationProbe
from pace_probe import StopProbe
image=Path('re/application_initialized_segments.bin').read_bytes()
p=ApplicationProbe(Path('firmware/FLASH_U202.bin').read_bytes())
p.ram[:len(image)]=image;p.r[29]=0x801ff000
p.r[4:7]=[0x20,0,1];p.pc=0x800296f0;p.mode16=True
for _ in range(40):
    if p.pc==0x8002b448:break
    p.step16()
else:raise AssertionError('Original builder did not call serial sender')
assert p.r[5]==6
address=p.r[4]&0x1fffffff
body=bytes(p.ram[address:address+6]);assert body==bytes.fromhex('050053200001'),body.hex()
p.handle_request(body)
assert p.replies[-1]['reply']=='020010'
assert p.peer_selector_outputs=={'20':'0001'}
assert not p.transport_ack_unknown
try:p.handle_request(bytes.fromhex('03015402'))
except StopProbe:pass
else:raise AssertionError('Unknown command must stop the default profile')
print('PASS: genuine command53 builder has3 byte arguments; ACK carries no device data; unknown command stops by default')
