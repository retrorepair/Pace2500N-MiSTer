"""Compare independently extracted segments with original startup execution."""
from pathlib import Path
import argparse,gzip,pickle,json
from extract_application_ram import extract

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',default='re/application_entry_02.pkl.gz');ap.add_argument('--out',default='re/application_extraction_comparison.json');a=ap.parse_args()
    image,segments=extract(Path('firmware/FLASH_U202.bin').read_bytes())
    with gzip.open(a.snapshot,'rb') as f:p=pickle.load(f)
    assert p.entrypoint_experiment and p.steps>=11250000,'Use a completed startup-decompression snapshot'
    comparisons=[]
    for s in segments:
        start=int(s['destination'],16)&0x1fffffff;end=start+s['output_bytes']
        differences=[i for i in range(start,end) if image[i]!=p.ram[i]]
        comparisons.append(dict(destination=s['destination'],bytes=end-start,differences=len(differences),first_offsets=[f'{i:06X}' for i in differences[:16]]))
    result=dict(steps=p.steps,pc=f'{p.pc:08X}',comparisons=comparisons)
    Path(a.out).write_text(json.dumps(result,indent=2)+'\n')
    assert all(c['differences']==0 for c in comparisons),result
    print('PASS: all5 initialized segments match original MIPS startup execution byte-for-byte, including1029152 decompressed bytes')
