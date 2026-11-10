"""Extract U202's initialized application segments using its original startup.

Implements the copy table and dictionary/mask halfword decoder at20618..20764.
This is an analysis artifact, not a replacement firmware or a boot accelerator.
"""
from pathlib import Path
import argparse,json,hashlib

def extract(flash):
    def word(offset):return int.from_bytes(flash[offset:offset+4],'big')
    segments=[];image=bytearray(16*1024*1024)
    for entry in range(0x211dc,0x21218,12):
        destination,source,length=(word(entry+n) for n in (0,4,8))
        offset=source&0x1fffffff;offset-=0x1fc00000
        assert 0<=offset<len(flash) and destination&0x1fffffff<len(image)
        start=offset
        if source==0x9fcd06f0 and flash[offset]==0:
            groups=word(offset);dictionary=flash[offset+4:offset+0x204];offset+=0x204
            data=bytearray()
            for _ in range(groups):
                mask=int.from_bytes(flash[offset:offset+2],'big');offset+=2
                for bit in range(15,-1,-1):
                    if mask&(1<<bit):
                        index=flash[offset];offset+=1
                        data.extend(dictionary[index*2:index*2+2])
                    else:data.extend(flash[offset:offset+2]);offset+=2
            encoding='dictionary halfwords,16-bit masks'
        else:data=flash[offset:offset+length];offset+=length;encoding='raw'
        destination_offset=destination&0x1fffffff
        assert destination_offset+len(data)<=len(image)
        image[destination_offset:destination_offset+len(data)]=data
        segments.append(dict(destination=f'{destination:08X}',source=f'{source:08X}',
            declared_bytes=length,output_bytes=len(data),source_bytes=offset-start,
            encoding=encoding,sha256=hashlib.sha256(data).hexdigest()))
    end=max((int(s['destination'],16)&0x1fffffff)+s['output_bytes'] for s in segments)
    return bytes(image[:end]),segments

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='re/application_initialized_segments');a=ap.parse_args()
    flash=Path('firmware/FLASH_U202.bin').read_bytes();data,segments=extract(flash)
    Path(a.out+'.bin').write_bytes(data)
    r=dict(firmware_sha256=hashlib.sha256(flash).hexdigest(),base='80000000',
        artifact='Initialized segments only; zero gaps are not recovered BSS contents',
        bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),segments=segments)
    Path(a.out+'.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))
