"""Generate/compare unaligned merge cases against independent Ghidra p-code."""
import argparse,json,random
from pathlib import Path
from pace_probe_research import ResearchProbe
ap=argparse.ArgumentParser();ap.add_argument('--generate',action='store_true');a=ap.parse_args()
source=Path('re/unaligned_oracle_cases.json');result=Path('re/unaligned_oracle_results.json')
def word(op,rt=3,imm=0):return ((op<<26)|(2<<21)|(rt<<16)|(imm&65535)).to_bytes(4,'big').hex()
if a.generate:
    rng=random.Random(3216);cases=[]
    for op in (34,38,42,46):
        for offset in range(4):
            for delay in (False,True):
                code=word(op)
                if delay:code='10000004'+code
                cases.append(dict(id=f'op{op}_offset{offset}_delay{int(delay)}',isa_mode=0,
                    pc='80002000',code=code,steps=1,cpu_steps=2 if delay else 1,
                    regs={'v0':f'{0x80003004+offset:08x}','v1':f'{rng.getrandbits(32):08x}'},
                    memory={'80003000':rng.randbytes(16).hex()},read_ranges=[dict(address='80003000',length=16)]))
    for offset in range(4):
        cases.append(dict(id=f'paired_store_load_{offset}',isa_mode=0,pc='80002000',
            code=word(42)+word(46,imm=3)+word(34,rt=4)+word(38,rt=4,imm=3),steps=4,
            regs={'v0':f'{0x80003004+offset:08x}','v1':'12345678','a0':'deadbeef'},
            memory={'80003000':'a5'*16},read_ranges=[dict(address='80003000',length=16)]))
    source.write_text(json.dumps(cases,indent=2));print('Generated',len(cases),'Ghidra cases')
else:
    cases=json.loads(source.read_text());results=json.loads(result.read_text());assert len(cases)==len(results)
    for c,r in zip(cases,results):
        assert r['id']==c['id'] and r['status']=='ok',r
        p=ResearchProbe(bytes(2097152));p.pc=int(c['pc'],16);p.mode16=False
        for address,data in {c['pc']:c['code'],**c['memory']}.items():
            start=int(address,16)&0x1fffffff;p.ram[start:start+len(data)//2]=bytes.fromhex(data)
        for reg,index in [('v0',2),('v1',3),('a0',4)]:p.r[index]=int(c['regs'].get(reg,'0'),16)
        for _ in range(c.get('cpu_steps',c['steps'])):p.step32()
        assert p.pc==int(r['pc'],16),(c['id'],'PC',hex(p.pc),r['pc'])
        for reg,index in [('v0',2),('v1',3),('a0',4)]:assert p.r[index]==int(r['regs'][reg],16),(c['id'],reg)
        assert p.ram[0x3000:0x3010].hex()==r['memory']['80003000'],c['id']
    print('PASS:',len(cases),'Ghidra oracle cases, all offsets, four merge operations, delay slots and paired unaligned store/load')
