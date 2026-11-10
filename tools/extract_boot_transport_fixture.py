"""Extract U202's six-packet transport fixture and independently assemble PSI.

Compare section bytes with the firmware's expected DMA buffers. This script
does not patch the firmware or claim an EMMA demux register implementation.
"""
from pathlib import Path
import hashlib,json
f=Path('firmware/FLASH_U202.bin').read_bytes()
stream=f[0x1b188:0x1b188+6*188]
pending={};sections=[]
def crc32_mpeg(data):
    crc=0xffffffff
    for byte in data:
        crc^=byte<<24
        for _ in range(8):crc=((crc<<1)^ (0x04c11db7 if crc&0x80000000 else 0))&0xffffffff
    return crc
def append(pid,data):
    pending.setdefault(pid,bytearray()).extend(data)
    buf=pending[pid]
    while len(buf)>=3:
        if buf[0]==0xff:buf.clear();break
        length=3+((buf[1]&15)<<8)+buf[2]
        assert length<=4096
        if len(buf)<length:break
        raw=bytes(buf[:length]);del buf[:length]
        sections.append(dict(pid=pid,bytes=length,table_id=raw[0],extension=int.from_bytes(raw[3:5],'big'),crc_ok=crc32_mpeg(raw)==0,data=raw.hex(),
                             sha256=hashlib.sha256(raw).hexdigest()))
packets=[]
for n in range(6):
    p=stream[n*188:(n+1)*188];assert p[0]==0x47 and (p[3]>>4)&3==1
    pid=((p[1]&31)<<8)|p[2];payload=p[4:]
    packets.append(dict(index=n,pid=pid,pusi=bool(p[1]&0x40),continuity=p[3]&15))
    if p[1]&0x40:
        pointer=payload[0]
        if pointer:append(pid,payload[1:1+pointer])
        assert not pending.get(pid),f'Incomplete section at PUSI boundary PID{pid}'
        append(pid,payload[1+pointer:])
    else:append(pid,payload)
expected=[f[0x1b77c:0x1b834],f[0x1b834:0x1b8e8]]
matches=[]
for number,target in enumerate(expected):
    for mask in range(1,1<<len(sections)):
        selected=[n for n in range(len(sections)) if mask>>n&1]
        for alignment in (1,4):
            # Observed expected buffers end each section with the output
            # channel byte, followed by zero padding to a 32-bit boundary.
            joined=b''.join(bytes.fromhex(sections[n]['data'])+bytes([number])+bytes((-(sections[n]['bytes']+1))%alignment) for n in selected)
            if joined==target:matches.append(dict(buffer=number,sections=selected,alignment=alignment))
reconstructed=[]
for output,extension in ((0,1),(1,0)):
    # PID0 is one matching choice; PID1 duplicates the same section bytes in
    # this fixture, so payload equality alone cannot determine PID routing.
    selected=[s for s in sections if s['pid']==0 and s['crc_ok'] and s['extension']==extension]
    data=b''.join(bytes.fromhex(s['data'])+bytes([output]) for s in selected)
    assert data==expected[output],f'Firmware expected DMA buffer{output} differs'
    reconstructed.append(dict(output=output,bytes=len(data),exact_match=True))
report=dict(packets=packets,sections=sections,pending_bytes={str(k):len(v) for k,v in pending.items()},expected_buffer_matches=matches,reconstructed_buffers=reconstructed)
Path('re/transport_fixture_sections.json').write_text(json.dumps(report,indent=2)+'\n')
Path('re/boot_transport_fixture.ts').write_bytes(stream)
print('Packets:',packets)
print('Sections:',[(n,x['pid'],x['table_id'],x['bytes'],x['extension'],x['crc_ok']) for n,x in enumerate(sections)])
print('Expected buffer matches:',matches)
print('PASS: both genuine expected buffers reconstructed exactly:',reconstructed)
