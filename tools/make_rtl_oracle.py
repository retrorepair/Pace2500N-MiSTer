"""Translate independently captured Ghidra results into RTL stimulus/checks."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
names='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp s8 ra'.split()
results={x['id']:x for x in json.loads((root/'re/oracle_results.json').read_text())}
lines=[]
for index,c in enumerate(json.loads((root/'re/oracle_cases.json').read_text())):
    r=results[c['id']];assert r['status']=='ok'
    pc=int(c.get('pc','bfc1f000'),16);mode=c.get('isa_mode',1);code=bytes.fromhex(c['code'])
    i=int.from_bytes(code[:2],'big')
    count=c.get('research_steps',c.get('steps',1))
    if mode and (i>>11==3 or (i>>11==29 and i&31==0 and not i&0x80)):count+=1
    if not mode and int.from_bytes(code[:4],'big')&0xfc00003f in (8,9):count+=1
    lines.append(f'// {index}: {c["id"]}\ninit_case({index},32\'h{pc:08x},1\'b{mode});')
    for n,v in enumerate(code):lines.append(f'put_byte(32\'h{pc+n:08x},8\'h{v:02x});')
    for addr,value in c.get('memory',{}).items():
        for n,v in enumerate(bytes.fromhex(value)):lines.append(f'put_byte(32\'h{int(addr,16)+n:08x},8\'h{v:02x});')
    for name,value in c['regs'].items():lines.append(f'DUT.gpr[{names.index(name)}]=32\'h{value};')
    for name in ('hi','lo'):lines.append(f'DUT.{name}=32\'h{c.get(name,"00000000")};')
    lines.append(f'execute_case({count});')
    for n,name in enumerate(names):lines.append(f'check_reg({n},32\'h{r["regs"][name]});')
    lines.append(f'''if(DUT.pc!==32'h{r['pc']} || DUT.mips16!==1'b{r['isa_mode']} || DUT.hi!==32'h{r['regs']['hi']} || DUT.lo!==32'h{r['regs']['lo']})
 $fatal(1,"case %0d state PC=%h mode=%b HI=%h LO=%h",case_id,DUT.pc,DUT.mips16,DUT.hi,DUT.lo);''')
    for addr,value in r.get('memory',{}).items():
        for n,v in enumerate(bytes.fromhex(value)):lines.append(f'check_byte(32\'h{int(addr,16)+n:08x},8\'h{v:02x});')
(root/'sim/oracle_cases.svh').write_text('\n'.join(lines)+'\n')
print(f'Generated {len(results)} RTL oracle cases')
