"""Verify real application headers and payloads with U202's CRC convention."""
from pathlib import Path
import json,hashlib
from pace_crc_accel import crc
report=[]
for path in Path('firmware').glob('FLASH_U20?.bin'):
    data=path.read_bytes();base=0x20000
    size=int.from_bytes(data[base+8:base+12],'big')
    header=crc(data[base:base+32]);payload=crc(data[base+36:base+36+size])
    assert base+36+size<=len(data) and header==payload==0
    report.append(dict(file=path.name,sha256=hashlib.sha256(data).hexdigest(),payload_bytes=size,header_crc=f'{header:08X}',payload_crc=f'{payload:08X}'))
Path('re/firmware_application_crc.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: both genuine application headers/payloads validate with zero CRC')
