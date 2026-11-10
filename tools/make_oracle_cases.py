"""Create independent Ghidra p-code differential cases for the research CPU."""
from pathlib import Path
import json
import random

root=Path(__file__).resolve().parents[1]
cases=[]
registers=['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7',
           's0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','s8','ra']
compressed=['s0','s1','v0','v1','a0','a1','a2','a3']
rng=random.Random(2500)
def add(name,words,regs=None,**kwargs):
    initial={name:f'{rng.getrandbits(32):08x}' for name in registers[1:]}
    initial.update(sp='80001000',ra='bfc1f200')
    initial.update(regs or {})
    cases.append(dict(id=name,code=''.join(f'{w:04x}' for w in words),regs=initial,**kwargs))

add('shift_distinct',[0x3274],{'v1':'00000003','v0':'abcdef01'})
add('extended_shift16',[0xf400,0x36c0],{'a2':'00001234'})
add('extended_store_real',[0xf140,0xdf60],{'a3':'80000000','v1':'11223344'},read_ranges=[dict(address='80000140',length=4)])
add('load_distinct',[0x9f40],{'a3':'80000000'},memory={'80000000':'89abcdef'})
add('compact_return',[0xe8a0,0x6a55],{'ra':'bfc1f200','v0':'00000000'})
add('jr_delay',[0xe820,0x0a01],{'ra':'bfc1f200'})
add('normal_pc',[0x0a01])
add('extended_pc',[0xf000,0x0a03],pc='bfc1f002')
add('li_ffff',[0xf7ff,0x6a1f])
for fn in [2,3,4,6,7,10,11,12,13,14,15,16,18,24,25,26,27]:
    add(f'rr_{fn}',[(29<<11)|(2<<8)|((0 if fn in (16,18) else 3)<<5)|fn],{'v0':'80000003','v1':'00000007'})
for op in [0,1,8,9,10,11,13,14]:
    add(f'imm_{op}',[(op<<11)|(2<<8)|0x80])
    if op!=8:add(f'ext_{op}',[0xf7ff,(op<<11)|(2<<8)|0x1f])
for fn in [0,2,3]:
    for amount in [1,3,7,8]:
        add(f'shift_{fn}_{amount}',[(6<<11)|(2<<8)|(3<<5)|((amount%8)<<2)|fn],{'v1':'87654321'})
for source in range(8):
    destination=31-source
    code=(12<<11)|(5<<8)|((destination&7)<<5)|(destination&0x18)|source
    add(f'move_full_{source}',[code])

def extend(value):
    value&=0xffff
    return 0xf000|((value>>11)&31)|(value&0x7e0),value&31
for value in [0,1,31,32,255,256,1023,0x7fff,0x8000,0xffff]:
    prefix,low=extend(value)
    for op in [0,1,9,10,11,13,14]:
        add(f'ext_random_{op}_{value}',[prefix,(op<<11)|(2<<8)|low],pc='bfc1f002' if value&1 else 'bfc1f000')
for op,size in [(16,1),(17,2),(19,4),(20,1),(21,2),(24,1),(25,2),(27,4)]:
    for offset in [0,size,32,-32,256,-256]:
        rx,ry=rng.sample(range(8),2)
        prefix,low=extend(offset)
        address=0x80001000+offset
        initial={compressed[rx]:'80001000',compressed[ry]:'89abcdef'}
        data=bytes(rng.randrange(256) for _ in range(8)).hex()
        add(f'memory_{op}_{offset}',[prefix,(op<<11)|(rx<<8)|(ry<<5)|low],initial,
            memory={f'{address:08x}':data},read_ranges=[dict(address=f'{address:08x}',length=8)])
for amount in [0,1,7,8,16,24,31]:
    for fn in [0,2,3]:
        add(f'extended_shift_{fn}_{amount}',[0xf000|(amount<<6),(6<<11)|(2<<8)|(3<<5)|fn],{'v1':'87654321'})
for value in [-16384,-17,-1,0,1,15,16,16383]:
    packed=value&0x7fff
    prefix=0xf000|((packed>>11)&15)|(packed&0x7f0)
    add(f'rria_ext_{value}',[prefix,(8<<11)|(2<<8)|(3<<5)|(packed&15)],{'v0':'12345678'})
for op in [2,4,5]:
    for offset in [-4,0,4,100]:
        prefix,low=extend(offset)
        add(f'branch_{op}_{offset}',[prefix,(op<<11)|((2<<8) if op!=2 else 0)|low],{'v0':'00000000'})
for start in [0xbfc1f000,0xbfc1f002]:
    target=0xbfc1f200
    first=0x1800|((target>>23)&31)|(((target>>18)&31)<<5)
    add(f'jal_delay_pc_{start:x}',[first,(target>>2)&0xffff,0x0a01],pc=f'{start:08x}')
for fn in [4,6,7,16,17,18,19,24,25,26,27]:
    add(f'mips32_{fn}',[],{'v0':'80000003','v1':'00000007'},isa_mode=0)
    fields=(4<<11) if fn in (16,18) else (2<<21) if fn in (17,19) else (2<<21)|(3<<16) if fn>=24 else (2<<21)|(3<<16)|(4<<11)
    cases[-1]['code']=f'{fields|fn:08x}'
for rd in [0,4,31]:
    add(f'mips32_jalr_{rd}',[],{'v0':'bfc1f201'},isa_mode=0)
    cases[-1]['code']=f'{(2<<21)|(rd<<11)|9:08x}'+'00000000'
for rt in [0,1,2,3,16,17,18,19]:
    for value in [0x80000000,0,1]:
        take=(value<0x80000000) if rt&1 else (value>=0x80000000)
        add(f'regimm_{rt}_{value:x}',[],{'v0':f'{value:08x}'},isa_mode=0)
        cases[-1]['code']=f'{(1<<26)|(2<<21)|(rt<<16)|3:08x}'+'24630001'
        cases[-1]['research_steps']=1 if rt&2 and not take else 2
(root/'re/oracle_cases.json').write_text(json.dumps(cases,indent=2)+'\n')
print('Oracle cases:',len(cases))
