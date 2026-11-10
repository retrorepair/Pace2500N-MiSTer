#!/usr/bin/env python3
"""Research MIPS16 interpreter; hardware responses remain explicitly experimental.

Keep the v0.4.4 checkpoint interpreter intact. Encoding/semantics cross-checked
against Ghidra MIPS16 Sleigh and MIPS MD00076, rather than copying the RTL.
"""
import argparse
from collections import deque, Counter
import json
from pathlib import Path
from pace_probe import Probe, StopProbe, GPR16, U32, sign, get_flash


class ResearchProbe(Probe):
    def __init__(self, *args, read_overrides=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.extended_count=0
        self.recent=deque(maxlen=2048)
        self.calls=deque(maxlen=256)
        self.mmio_streams={}
        self.hi=0;self.lo=0
        self.visits=Counter()
        self.read_overrides=dict(read_overrides or {})
        self.llbit=False
        self.recent_mmio=deque(maxlen=2048)
        for address in self.read_overrides:
            assert address&0xfff00000 in (0xb0000000,0xb2000000),'Override only an explicitly selected MMIO address'

    @staticmethod
    def memory_kind(address,size):
        if (0x80000000<=address and address+size<=0x81000000) or (0xa0000000<=address and address+size<=0xa1000000):return 'ram'
        if (0xbfc00000<=address and address+size<=0xbfe00000) or (0x9fc00000<=address and address+size<=0x9fe00000):return 'flash'
        if address&0xfff00000 in (0xb0000000,0xb2000000):return 'mmio'
        return None

    def read(self,address,size=4):
        address&=U32
        if size in (2,4) and address%size:raise StopProbe(f'Unaligned read {size}B at {address:08X}, PC={self.pc:08X}')
        if self.memory_kind(address,size) is None:raise StopProbe(f'Unmapped read {size}B at {address:08X}, PC={self.pc:08X}')
        if self.memory_kind(address,size)=='mmio' and ('read',address,size) not in self.mmio:
            self.recent_mmio.append(dict(step=self.steps,pc=f'{self.pc:08X}',kind='first_read',address=f'{address:08X}',size=size))
        if address in self.read_overrides:
            key=('read',address,size);self.mmio[key]+=1
            value=self.read_overrides[address]&((1<<(size*8))-1)
            if self.mmio[key]==1:self.mmio_first.append((self.steps,'read',address,size,value))
            return value
        return super().read(address,size)

    def write(self,address,value,size=4):
        address&=U32
        if size in (2,4) and address%size:raise StopProbe(f'Unaligned write {size}B at {address:08X}, PC={self.pc:08X}')
        kind=self.memory_kind(address,size)
        if kind not in ('ram','mmio'):raise StopProbe(f'Unsupported {kind or "unmapped"} write {size}B at {address:08X}, PC={self.pc:08X}')
        if kind=='mmio':
            self.mmio_streams.setdefault((address,size),deque(maxlen=4096)).append(value&((1<<(size*8))-1))
            self.recent_mmio.append(dict(step=self.steps,pc=f'{self.pc:08X}',kind='write',address=f'{address:08X}',size=size,value=f'{value&((1<<(size*8))-1):08X}'))
        return super().write(address,value,size)

    def log(self, text):
        super().log(text)
        self.recent.append(text)

    def call_snapshot(self,source,target,kind):
        self.calls.append({'step':self.steps,'from':f'{source:08X}','to':f'{target:08X}',
                           'kind':kind,'args':[f'{v:08X}' for v in self.r[4:8]],'sp':f'{self.r[29]:08X}'})

    def step32(self):
        p=self.pc;i=self.read(p,4);op=i>>26;fn=i&63
        self.recent.append(f'{self.steps:8d} {p:08X} {i:08X} MIPS32')
        rs=(i>>21)&31;rt=(i>>16)&31;rd=(i>>11)&31
        a,b=self.r[rs],self.r[rt]
        if op in (34,38,42,46): # big-endian LWL/LWR/SWL/SWR
            address=(a+sign(i&0xffff,16))&U32;aligned=address&~3;offset=address&3
            if self.memory_kind(aligned,4)!='ram':
                raise StopProbe(f'Unaligned merge outside RAM at {address:08X}')
            value=bytearray(b.to_bytes(4,'big'))
            if op==34:
                value[:4-offset]=bytes(self.read(n,1) for n in range(address,aligned+4))
            elif op==38:
                value[3-offset:]=bytes(self.read(n,1) for n in range(aligned,address+1))
            elif op==42:
                for n,byte in enumerate(value[:4-offset]):self.write(address+n,byte,1)
            else:
                for n,byte in enumerate(value[3-offset:]):self.write(aligned+n,byte,1)
            if op in (34,38) and rt:self.r[rt]=int.from_bytes(value,'big')
            self.unique32.add(p);self.pc=self.branch if self.branch is not None else (p+4)&U32
            self.branch=None;self.r[0]=0;self.steps+=1;return
        if op==1 and rt in (0,1,2,3,16,17,18,19):
            if self.branch is not None:raise StopProbe(f'REGIMM in branch delay slot at {p:08X}')
            take=(sign(a,32)>=0) if rt&1 else (sign(a,32)<0)
            if rt&16:self.r[31]=(p+8)&U32
            likely=bool(rt&2)
            self.branch=(p+4+(sign(i&0xffff,16)<<2))&U32 if take else None
            self.pc=(p+(8 if likely and not take else 4))&U32
            self.unique32.add(p);self.r[0]=0;self.steps+=1
            return
        if i==0x42000018:
            if self.branch is not None:raise StopProbe(f'ERET in branch delay slot at {p:08X}')
            status=self.cp0.get(12,0)
            if status&4:target=self.cp0.get(30,0);status&=~4
            else:target=self.cp0.get(14,0);status&=~2
            self.cp0[12]=status;self.llbit=False
            self.unique32.add(p);self.pc=target&~1;self.mode16=bool(target&1);self.branch=None;self.steps+=1
            self.mode_switches.append((self.steps,p,self.pc,'ERET->'+('MIPS16' if self.mode16 else 'MIPS32')))
            return
        if op==0 and fn in (8,9):
            if self.branch is not None:raise StopProbe(f'Jump in branch delay slot at {p:08X}')
            target=a
            if fn==9 and rd:self.r[rd]=(p+8)&U32
            self.unique32.add(p);self.pc=(p+4)&U32;self.steps+=1
            self.step32()
            self.pc=target&~1;self.mode16=bool(target&1);self.branch=None
            self.mode_switches.append((self.steps,p,self.pc,'MIPS32->'+('MIPS16' if self.mode16 else 'MIPS32')))
            if fn==9:self.call_snapshot(p,self.pc,'jalr32')
            return
        if op==0 and fn in (4,6,7,16,17,18,19,24,25,26,27):
            self.unique32.add(p)
            def wr(value):
                if rd:self.r[rd]=value&U32
            if fn==4:wr(b<<(a&31))
            elif fn==6:wr(b>>(a&31))
            elif fn==7:wr(sign(b,32)>>(a&31))
            elif fn==16:wr(self.hi)
            elif fn==17:self.hi=a
            elif fn==18:wr(self.lo)
            elif fn==19:self.lo=a
            elif fn in (24,25):
                aa,bb=(sign(a,32),sign(b,32)) if fn==24 else (a,b)
                product=(aa*bb)&0xffffffffffffffff;self.hi=product>>32;self.lo=product&U32
            else:
                aa,bb=(sign(a,32),sign(b,32)) if fn==26 else (a,b)
                if bb==0:raise StopProbe(f'Division by zero at {p:08X}')
                q=abs(aa)//abs(bb);q=-q if (aa<0)!=(bb<0) else q
                self.lo=q&U32;self.hi=(aa-q*bb)&U32
            self.pc=self.branch if self.branch is not None else (p+4)&U32
            self.branch=None;self.r[0]=0;self.steps+=1
            return
        return super().step32()

    def step16(self):
        p=self.pc
        self.visits[p]+=1
        first=self.read(p,2)
        prefix=first if first>>11==30 else None
        length=4 if prefix is not None else 2
        i=self.read(p+2,2) if prefix is not None else first
        if prefix is not None and self.pc_relative_base is not None:
            raise StopProbe(f'Unpredictable EXTEND in jump delay slot at {p:08X}')
        op=i>>11; rx=(i>>8)&7; ry=(i>>5)&7; rz=(i>>2)&7
        imm8=i&255; imm5=i&31
        imm16=(((prefix&31)<<11)|(prefix&0x7e0)|imm5) if prefix is not None else None
        simm=sign(imm16,16) if imm16 is not None else None
        base=p if self.pc_relative_base is None else self.pc_relative_base
        r=lambda index:self.r[GPR16[index]]
        def wr(index,value): self.r[GPR16[index]]=value&U32
        def full(index,value):
            if index:self.r[index]=value&U32
        self.unique16.add(p);self.mips16_count+=1
        if prefix is not None:self.extended_count+=1
        if len(self.pc16_sample)<100:self.pc16_sample.append((p,first))
        nextpc=(p+length)&U32
        desc=''
        if op==3 and prefix is None:
            second=self.read(p+2,2)
            target=(((p+4)&0xf0000000)|((((i&31)<<21)|(((i>>5)&31)<<16)|second)<<2))&U32
            self.r[31]=(p+6)|1
            self.log(f'{self.steps:8d} {p:08X} {i:04X} {second:04X} MIPS16 JALX/JAL -> {target:08X}')
            self.steps+=1
            self.step16_delay(p+4,p)
            self.pc=target;self.mode16=not bool(i&0x400)
            self.mode_switches.append((self.steps,p,target,'MIPS16->'+('MIPS16' if self.mode16 else 'MIPS32')))
            self.call_snapshot(p,target,'jal16')
            return
        if op==0:
            wr(rx,self.r[29]+(simm if prefix is not None else imm8<<2));desc='addiu rx,sp'
        elif op==1:
            wr(rx,((p&~3)+simm) if prefix is not None else ((base+(imm8<<2))&~3));desc='addiupc'
        elif op==2:
            nextpc=(nextpc+((simm if prefix is not None else sign(i&0x7ff,11))<<1))&U32;desc='b'
        elif op in (4,5):
            if (r(rx)==0)==(op==4):nextpc=(nextpc+((simm if prefix is not None else sign(imm8,8))<<1))&U32
            desc='beqz' if op==4 else 'bnez'
        elif op==6:
            sh=((prefix>>6)&31) if prefix is not None else (((i>>2)&7) or 8)
            if prefix is not None and ((prefix&0x3f) or (i&0x1c)):
                raise StopProbe(f'Reserved extended SHIFT {first:04X} {i:04X} at {p:08X}')
            fn=i&3
            if fn==0:wr(rx,r(ry)<<sh)
            elif fn==2:wr(rx,r(ry)>>sh)
            elif fn==3:wr(rx,sign(r(ry),32)>>sh)
            else:raise StopProbe(f'Unsupported SHIFT {i:04X} at {p:08X}')
            desc=f'shift fn={fn}, amount={sh}'
        elif op==8:
            if i&16:raise StopProbe(f'Unsupported DADDIU {i:04X} at {p:08X}')
            immediate=sign(((prefix&15)<<11)|(prefix&0x7f0)|(i&15),15) if prefix is not None else sign(i&15,4)
            wr(ry,r(rx)+immediate);desc='addiu ry,rx,imm'
        elif op==9:wr(rx,r(rx)+(simm if prefix is not None else sign(imm8,8)));desc='addiu rx,imm'
        elif op in (10,11):
            immediate=imm16 if prefix is not None else imm8
            self.r[24]=int((sign(r(rx),32)<immediate) if op==10 else r(rx)<immediate)
            desc='slti' if op==10 else 'sltiu'
        elif op==12:
            if rx in (0,1):
                if (self.r[24]==0)==(rx==0):nextpc=(nextpc+((simm if prefix is not None else sign(imm8,8))<<1))&U32
                desc='bteqz' if rx==0 else 'btnez'
            elif rx==2:
                self.write((self.r[29]+(simm if prefix is not None else imm8<<2))&U32,self.r[31],4);desc='sw ra,sp'
            elif rx==3:
                self.r[29]=(self.r[29]+(simm if prefix is not None else sign(imm8,8)<<3))&U32;desc='addiu sp'
            elif rx==5 and prefix is None:
                # Destination: bits[4:3] are register[4:3], bits[7:5] register[2:0].
                full((i&0x18)|ry,r(i&7));desc='move full,compressed'
            elif rx==7 and prefix is None:wr(ry,self.r[i&31]);desc='move compressed,full'
            else:raise StopProbe(f'Unsupported MIPS16 I8 {i:04X} at {p:08X}')
        elif op==13:wr(rx,imm16 if prefix is not None else imm8);desc='li'
        elif op==14:self.r[24]=r(rx)^(imm16 if prefix is not None else imm8);desc='cmpi'
        elif op in (16,17,19,20,21,24,25,27):
            size={16:1,17:2,19:4,20:1,21:2,24:1,25:2,27:4}[op]
            offset=simm if prefix is not None else imm5*size
            address=(r(rx)+offset)&U32
            if op>=24:self.write(address,r(ry),size)
            else:
                value=self.read(address,size)
                wr(ry,sign(value,size*8) if op in (16,17) else value)
            desc=f'{"store" if op>=24 else "load"}{size} base=r{GPR16[rx]} reg=r{GPR16[ry]} @{address:08X}'
        elif op in (18,26):
            address=(self.r[29]+(simm if prefix is not None else imm8<<2))&U32
            if op==18:wr(rx,self.read(address,4))
            else:self.write(address,r(rx),4)
            desc='lwsp' if op==18 else 'swsp'
        elif op==22:
            address=((p+simm)&~3) if prefix is not None else ((base+(imm8<<2))&~3)
            wr(rx,self.read(address&U32,4));desc=f'lwpc @{address&U32:08X}'
        elif op==28 and prefix is None:
            if i&3==1:wr(rz,r(rx)+r(ry));desc='addu'
            elif i&3==3:wr(rz,r(rx)-r(ry));desc='subu'
            else:raise StopProbe(f'Unsupported MIPS16 RRR {i:04X} at {p:08X}')
        elif op==29 and prefix is None:
            fn=i&31
            if fn==0:
                target=self.r[31] if i&0x20 else r(rx)
                nd=bool(i&0x80);link=bool(i&0x40)
                if link:self.r[31]=((p+2) if nd else (p+4))|1
                self.log(f'{self.steps:8d} {p:08X} {i:04X} MIPS16 {"jalr" if link else "jr"}{"c" if nd else ""} -> {target:08X}')
                self.steps+=1
                if not nd:self.step16_delay(p+2,p)
                self.pc=target&~1;self.mode16=bool(target&1);self.r[0]=0
                self.mode_switches.append((self.steps,p,self.pc,'MIPS16->'+('MIPS16' if self.mode16 else 'MIPS32')))
                if link:self.call_snapshot(p,self.pc,'jalr16')
                return
            elif fn in (2,3):self.r[24]=int(sign(r(rx),32)<sign(r(ry),32) if fn==2 else r(rx)<r(ry));desc='slt/sltu'
            elif fn in (4,6,7):
                amount=r(rx)&31
                wr(ry,r(ry)<<amount if fn==4 else r(ry)>>amount if fn==6 else sign(r(ry),32)>>amount);desc='variable shift'
            elif fn==10:self.r[24]=r(rx)^r(ry);desc='cmp'
            elif fn==11:wr(rx,-r(ry));desc='neg'
            elif fn in (12,13,14,15):
                a,b=r(rx),r(ry);wr(rx,a&b if fn==12 else a|b if fn==13 else a^b if fn==14 else ~b);desc='logic'
            elif fn==16 and ry==0:wr(rx,self.hi);desc='mfhi'
            elif fn==18 and ry==0:wr(rx,self.lo);desc='mflo'
            elif fn==17 and ry in (0,1,4,5):
                bits=8 if ry in (0,4) else 16;value=r(rx)&((1<<bits)-1)
                wr(rx,sign(value,bits) if ry>=4 else value);desc='zero/sign extend'
            elif fn in (24,25):
                a,b=(sign(r(rx),32),sign(r(ry),32)) if fn==24 else (r(rx),r(ry))
                product=(a*b)&0xffffffffffffffff;self.lo=product&U32;self.hi=product>>32;desc='mult/multu'
            elif fn in (26,27):
                a,b=(sign(r(rx),32),sign(r(ry),32)) if fn==26 else (r(rx),r(ry))
                if b==0:raise StopProbe(f'Division by zero at {p:08X}')
                q=abs(a)//abs(b);q=-q if (a<0)!=(b<0) else q
                self.lo=q&U32;self.hi=(a-q*b)&U32;desc='div/divu'
            else:raise StopProbe(f'Unsupported MIPS16 RR {i:04X} at {p:08X}')
        else:raise StopProbe(f'Unsupported research MIPS16 {first:04X} {i:04X} op={op} at {p:08X}')
        encoding=f'{first:04X} {i:04X}' if prefix is not None else f'{i:04X}'
        self.log(f'{self.steps:8d} {p:08X} {encoding} MIPS16 {desc}')
        self.pc=nextpc;self.r[0]=0;self.steps+=1

    def report(self):
        report=super().report()
        report['extended_mips16']=self.extended_count
        report['recent_trace']=list(self.recent)
        report['frequent_mips16_pc']=[{'pc':f'{p:08X}','count':count} for p,count in self.visits.most_common(16)]
        report['all_mmio_reads']=[{'address':f'{a:08X}','bytes':size,'count':count} for (kind,a,size),count in self.mmio.items() if kind=='read']
        report['experimental_zero_mmio']=self.unsafe_zero_mmio
        report['experimental_read_overrides']={f'{a:08X}':f'{v:08X}' for a,v in self.read_overrides.items()}
        report['recent_calls']=list(self.calls)
        report['recent_mmio']=list(self.recent_mmio)
        report['mmio_ascii_candidates']=[]
        for (address,size),values in self.mmio_streams.items():
            if len(values)>=4 and sum(v<256 and (32<=v<127 or v in (9,10,13)) for v in values)>len(values)//2:
                report['mmio_ascii_candidates'].append({'address':f'{address:08X}','bytes':size,
                    'text':''.join(chr(v) if v<256 else '?' for v in values)})
        return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('firmware');ap.add_argument('--steps',type=int,default=5000000)
    ap.add_argument('--out',default='research_probe.json')
    ap.add_argument('--unsafe-zero-mmio',action='store_true')
    ap.add_argument('--experimental-read',action='append',default=[],metavar='HEX_ADDRESS=HEX_VALUE')
    args=ap.parse_args()
    overrides={int(a,16):int(v,16) for a,v in (item.split('=') for item in args.experimental_read)}
    probe=ResearchProbe(get_flash(args.firmware),unsafe_zero_mmio=args.unsafe_zero_mmio,read_overrides=overrides)
    probe.run(args.steps)
    Path(args.out).write_text(json.dumps(probe.report(),indent=2)+'\n')
    print(f'{probe.steps:,} instructions | {probe.status} | PC {probe.pc:08X} | EXTEND {probe.extended_count}')
    print('Report:',args.out)

if __name__=='__main__':main()
