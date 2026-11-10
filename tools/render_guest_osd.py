"""Export an observed 8bpp OSD display list from a probe snapshot to PNG.

Uses guest field buffers and packed CLUT only; does not construct UI content.
Display-list layout cross-checked against GoRetroTv fa3a471 and guest RAM.
"""
import argparse, gzip, hashlib, json, pickle, struct, zlib
from pathlib import Path

def render(p, output):
    assert not getattr(p, 'graphics_unexecuted', 0), 'Unexecuted graphics commands invalidate pixels'
    values = p.mmio_streams.get((0xb0004200, 4))
    assert values, 'Guest has not written an OSD root'
    root = values[-1]
    assert root & 0x01000000, 'OSD is disabled'
    descriptor = root & 0xffffff
    def number(at, size=4):
        assert 0 <= at <= len(p.ram)-size
        return int.from_bytes(p.ram[at:at+size], 'big')
    height, width = number(descriptor+8, 2)+1, number(descriptor+10, 2)+1
    clut = number(descriptor+12) & 0xffffff
    evenword = number(descriptor+16)
    depth = 1 << ((evenword >> 25) & 3)
    assert depth == 8 and 1 < width <= 2048 and 1 < height <= 1152
    even, odd = evenword & 0xffffff, number(descriptor+20) & 0xffffff
    assert even and clut
    rows = []
    for y in range(height):
        at = ([even, odd][y & 1] + (y//2)*width) if odd else even+y*width
        assert at+width <= len(p.ram)
        rows.append(bytes(p.ram[at:at+width]))
    indices = b''.join(rows)
    palette = bytearray()
    for i in range(256):
        entry = number(clut+i*2, 2)
        luma = ((entry >> 8) & 63)*4
        cb, cr = ((entry >> 4) & 15)*16-128, (entry & 15)*16-128
        yy = 1.164*(luma-16)
        palette.extend(max(0, min(255, int(c))) for c in
                       (yy+1.596*cr, yy-.392*cb-.813*cr, yy+2.017*cb))
    def chunk(tag, data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB',width,height,8,3,0,0,0))
    png += chunk(b'PLTE',bytes(palette))
    png += chunk(b'IDAT',zlib.compress(b''.join(b'\0'+row for row in rows)))+chunk(b'IEND',b'')
    Path(output).write_bytes(png)
    metadata = dict(step=p.steps, source='guest RAM display list/field buffers/CLUT',
        protected_loader_handoff_observed=False, hardware_capture=False,
        host_firmware_patches=getattr(p,'diagnostic_firmware_patches',[]),
        root=f'{root:08X}', descriptor=f'{descriptor:08X}', width=width, height=height,
        depth=depth, even=f'{even:08X}', odd=f'{odd:08X}', clut=f'{clut:08X}',
        distinct_indices=len(set(indices)), index_sha256=hashlib.sha256(indices).hexdigest(),
        png_sha256=hashlib.sha256(png).hexdigest())
    Path(output+'.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('snapshot');ap.add_argument('output');a=ap.parse_args()
    with gzip.open(a.snapshot,'rb') as f:p=pickle.load(f)
    print(json.dumps(render(p,a.output),indent=2))
