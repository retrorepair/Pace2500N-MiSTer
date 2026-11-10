"""Compare research CPU registers/memory with independent Ghidra p-code."""
from pathlib import Path
import json
from pace_probe_research import ResearchProbe

root=Path(__file__).resolve().parents[1]
names=['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7',
       's0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','s8','ra']
cases={x['id']:x for x in json.loads((root/'re/oracle_cases.json').read_text())}
passed=0;skipped=[];failures=[]
for oracle in json.loads((root/'re/oracle_results.json').read_text()):
    case=cases[oracle['id']]
    if oracle['status']!='ok':
        skipped.append(dict(id=case['id'],reason=oracle['error']));continue
    image=bytearray(2097152);pc=int(case.get('pc','bfc1f000'),16);code=bytes.fromhex(case['code'])
    image[pc-0xbfc00000:pc-0xbfc00000+len(code)]=code
    for address,value in case.get('memory',{}).items():
        a=int(address,16)
        if 0xbfc00000<=a<0xbfe00000:image[a-0xbfc00000:a-0xbfc00000+len(value)//2]=bytes.fromhex(value)
    p=ResearchProbe(bytes(image));p.pc=pc;p.mode16=bool(case.get('isa_mode',1))
    for name,value in case['regs'].items():p.r[names.index(name)]=int(value,16)
    for address,value in case.get('memory',{}).items():
        if int(address,16)<0xbfc00000:
            offset=int(address,16)&0x1fffffff;data=bytes.fromhex(value)
            p.ram[offset:offset+len(data)]=data
    try:
        for _ in range(case.get('research_steps',case.get('steps',1))):
            if p.mode16:p.step16()
            else:p.step32()
        actual={name:f'{p.r[index]:08x}' for index,name in enumerate(names)}
        actual.update(hi=f'{p.hi:08x}',lo=f'{p.lo:08x}')
        differences={name:dict(actual=value,expected=oracle['regs'][name]) for name,value in actual.items() if value!=oracle['regs'][name]}
        if f'{p.pc:08x}'!=oracle['pc']:differences['pc']=dict(actual=f'{p.pc:08x}',expected=oracle['pc'])
        if 'isa_mode' in oracle and int(p.mode16)!=oracle['isa_mode']:differences['isa_mode']=dict(actual=int(p.mode16),expected=oracle['isa_mode'])
        for address,value in oracle.get('memory',{}).items():
            offset=int(address,16)&0x1fffffff;actual_memory=p.ram[offset:offset+len(value)//2].hex()
            if actual_memory!=value:differences[address]=dict(actual=actual_memory,expected=value)
        if differences:failures.append(dict(id=case['id'],differences=differences))
        else:passed+=1
    except Exception as exc:failures.append(dict(id=case['id'],error=str(exc)))
report=dict(passed=passed,skipped=skipped,failures=failures)
(root/'re/oracle_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if failures:raise SystemExit(1)
