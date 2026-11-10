#!/usr/bin/env python3
"""Pace 2500N firmware probe: real ROM, 32-bit MIPS and exploratory MIPS16.
Not a production CPU; no fake successful boot or fabricated register values.
"""
import argparse, collections, json, pathlib, sys, zipfile

U32 = 0xffffffff
GPR16 = (16, 17, 2, 3, 4, 5, 6, 7)
class StopProbe(Exception): pass

def sign(v,b):return v-(1<<b) if v & (1<<(b-1)) else v

def get_flash(path):
 p=pathlib.Path(path)
 if p.suffix.lower()=='.zip':
  with zipfile.ZipFile(p) as z:
   return z.read('FLASH_U202.bin')
 return p.read_bytes()

class Probe:
 def __init__(self,flash,events_limit=300,unsafe_zero_mmio=False):
  self.flash=flash;self.ram=bytearray(16*1024*1024);self.r=[0]*32;self.unsafe_zero_mmio=unsafe_zero_mmio
  self.pc=0xbfc00008;self.mode16=False;self.branch=None
  self.pc_relative_base=None
  self.cp0={};self.steps=0;self.mmio=collections.Counter();self.mmio_first=[]
  self.events=[];self.events_limit=events_limit;self.pc16_sample=[];self.mode_switches=[]
  self.unique32=set();self.unique16=set();self.mips16_ext=None
  self.mips16_count=0;self.max_ram_write=0;self.status='step limit'
 def log(self,s):
  if len(self.events)<self.events_limit:self.events.append(s)
 def read(self,a,n=4):
  a &= U32
  if 0xbfc00000<=a and a+n<=0xbfc00000+len(self.flash):return int.from_bytes(self.flash[a-0xbfc00000:a-0xbfc00000+n],'big')
  if 0x9fc00000<=a and a+n<=0x9fc00000+len(self.flash):return int.from_bytes(self.flash[a-0x9fc00000:a-0x9fc00000+n],'big')
  if (0x80000000<=a and a+n<=0x81000000) or (0xa0000000<=a and a+n<=0xa1000000):
   off=a&0x1fffffff;return int.from_bytes(self.ram[off:off+n],'big')
  key=('read',a,n);self.mmio[key]+=1
  if self.mmio[key]==1:self.mmio_first.append((self.steps,'read',a,n,0))
  if not self.unsafe_zero_mmio:raise StopProbe(f"Unmodelled MMIO read {n}B at 0x{a:08X} (PC 0x{self.pc:08X})")
  return 0 # explicit diagnostic option only; NOT an emulated peripheral
 def write(self,a,v,n=4):
  a &= U32;v&=(1<<(n*8))-1
  if (0x80000000<=a and a+n<=0x81000000) or (0xa0000000<=a and a+n<=0xa1000000):
   off=a&0x1fffffff;self.ram[off:off+n]=v.to_bytes(n,'big');self.max_ram_write=max(off+n,self.max_ram_write);return
  key=('write',a,n);self.mmio[key]+=1
  if self.mmio[key]==1:self.mmio_first.append((self.steps,'write',a,n,v))
 def step32(self):
  p=self.pc;i=self.read(p);op=i>>26;rs=i>>21&31;rt=i>>16&31;rd=i>>11&31;sh=i>>6&31;fn=i&63;imm=i&65535;s=sign(imm,16)
  a=self.r[rs];b=self.r[rt];w=lambda v:v&U32
  self.unique32.add(p)
  nextpc=w(p+4);branch=None;desc=''
  if op==0 and fn in (8,9) and (a&1):
   # MIPS32 JR/JALR with ISA mode bit set: switch back to compressed MIPS16
   target=a&~1
   if fn==9:self.r[rd or 31]=w(p+8)
   self.pc=p+4;self.steps+=1
   self.step32() # execute branch delay slot in current ISA
   self.pc=target;self.branch=None;self.mode16=True
   self.mode_switches.append((self.steps,p,target,'MIPS32->MIPS16 via JR'))
   return
  if op==29:
   # JALX MIPS32->MIPS16, mandatory on VR4110 based firmware.
   # The MIPS32 delay slot executes before changing ISA mode.
   target=((p+4)&0xf0000000)|((i&0x03ffffff)<<2)
   self.r[31]=w(p+8);self.pc=p+4;self.steps+=1
   self.log(f'{self.steps:8d} {p:08X} {i:08X} jalx 0x{target:08X}')
   self.step32()
   self.pc=target;self.branch=None;self.mode16=True
   self.mode_switches.append((self.steps, p, target, 'MIPS32->MIPS16'))
   self.log(f'    *** MODE SWITCH at 0x{p:08X} -> 0x{target:08X} (MIPS16)')
   return
  if i==0:desc='nop'
  elif op==15:self.r[rt]=imm<<16;desc='lui'
  elif op in (8,9):self.r[rt]=w(a+s);desc='addiu'
  elif op==13:self.r[rt]=a|imm;desc='ori'
  elif op==12:self.r[rt]=a&imm;desc='andi'
  elif op==14:self.r[rt]=a^imm;desc='xori'
  elif op==10:self.r[rt]=int(sign(a,32)<s);desc='slti'
  elif op==11:self.r[rt]=int(a<w(s));desc='sltiu'
  elif op==0:
   if fn==8:branch=a;desc='jr'
   elif fn==9:self.r[rd or 31]=w(p+8);branch=a;desc='jalr'
   elif fn in (32,33):self.r[rd]=w(a+b);desc='addu'
   elif fn in (34,35):self.r[rd]=w(a-b);desc='subu'
   elif fn==36:self.r[rd]=a&b;desc='and'
   elif fn==37:self.r[rd]=a|b;desc='or'
   elif fn==38:self.r[rd]=a^b;desc='xor'
   elif fn==39:self.r[rd]=w(~(a|b));desc='nor'
   elif fn==0:self.r[rd]=w(b<<sh);desc='sll'
   elif fn==2:self.r[rd]=b>>sh;desc='srl'
   elif fn==3:self.r[rd]=w(sign(b,32)>>sh);desc='sra'
   elif fn==42:self.r[rd]=int(sign(a,32)<sign(b,32));desc='slt'
   elif fn==43:self.r[rd]=int(a<b);desc='sltu'
   else:raise StopProbe(f'Unsupported MIPS32 SPECIAL 0x{i:08X} at 0x{p:08X}')
  elif op==16:
   if rs==4:self.cp0[rd]=b;desc='mtc0'
   elif rs==0:self.r[rt]=self.cp0.get(rd,0);desc='mfc0'
   else:raise StopProbe(f'Unsupported COP0 0x{i:08X} at 0x{p:08X}')
  elif op in (35,32,36,33,37):
   n={35:4,32:1,36:1,33:2,37:2}[op];v=self.read(w(a+s),n)
   if op in (32,33):v=w(sign(v,n*8))
   self.r[rt]=v;desc='load'
  elif op==47:desc='cache (not emulated)'
  elif op in (43,40,41):
   n={43:4,40:1,41:2}[op];self.write(w(a+s),b,n);desc='store'
  elif op in (4,5,6,7,1,20,21,22,23):
   if op in (4,20):take=a==b
   elif op in (5,21):take=a!=b
   elif op in (6,22):take=sign(a,32)<=0
   elif op in (7,23):take=sign(a,32)>0
   else:take=sign(a,32)<0 if rt==0 else sign(a,32)>=0
   if take:branch=w(p+4+(s<<2))
   if op in (20,21,22,23) and not take:nextpc=w(p+8)
   desc='branch'
  elif op in (2,3):
   branch=((p+4)&0xf0000000)|((i&0x3ffffff)<<2)
   if op==3:self.r[31]=w(p+8)
   desc='jump'
  else:raise StopProbe(f'Unsupported MIPS32 0x{i:08X} at 0x{p:08X} opcode={op}')
  if self.steps<110 or self.steps%500000==0 or (self.steps>3178500 and len(self.events)<self.events_limit):
   self.log(f'{self.steps:8d} {p:08X} {i:08X} {desc}')
  self.pc=self.branch if self.branch is not None else nextpc
  self.branch=branch;self.r[0]=0;self.steps+=1
 def step16_delay(self,slot,origin):
  saved=self.pc_relative_base;self.pc_relative_base=origin;self.pc=slot
  try:self.step16()
  finally:self.pc_relative_base=saved
 def step16(self):
  p=self.pc;i=self.read(p,2);op=i>>11;rx=i>>8&7;ry=i>>5&7;rz=i>>2&7;imm8=i&255;imm5=i&31
  self.unique16.add(p);self.mips16_count+=1
  if len(self.pc16_sample)<100:self.pc16_sample.append((p,i))
  r=lambda j:self.r[GPR16[j]]
  wr=lambda j,v:self.r.__setitem__(GPR16[j],v&U32)
  pcnext=p+2;desc=''
  base_pc=p if self.pc_relative_base is None else self.pc_relative_base
  if op==3: # two-halfword MIPS16 JAL / JALX (Ghidra encoding)
   second=self.read(p+2,2)
   target=((p+4)&0xf0000000)|((((i&31)<<21)|(((i>>5)&31)<<16)|second)<<2)
   target&=U32
   self.r[31]=(p+6)|1
   self.log(f'{self.steps:8d} {p:08X} {i:04X} {second:04X} MIPS16 JALX/JAL -> 0x{target:08X}')
   self.steps+=1
   self.step16_delay(p+4,p) # PC-relative delay-slot base is the JAL/JALX address
   self.pc=target;self.mode16=not bool(i&0x0400)
   self.mode_switches.append((self.steps,p,target,'MIPS16->'+('MIPS16' if self.mode16 else 'MIPS32')))
   return
  elif op==22: # lwpc: PC aligned, unsigned offset *4
   addr=(base_pc&~3)+(imm8<<2);wr(rx,self.read(addr,4));desc=f'lwpc r{GPR16[rx]}, [0x{addr:08X}]'
  elif op==19: # lw rx, offset(ry), offset *4
   addr=(r(ry)+(imm5<<2))&U32;wr(rx,self.read(addr,4));desc=f'lw r{GPR16[rx]}, [0x{addr:08X}]'
  elif op==21: # lhu rx, offset(ry), offset*2
   addr=(r(ry)+(imm5<<1))&U32;wr(rx,self.read(addr,2));desc=f'lhu r{GPR16[rx]}, [0x{addr:08X}]'
  elif op==0:wr(rx,self.r[29]+(sign(imm8,8)<<2));desc='addiusp'
  elif op==1:wr(rx,(base_pc&~3)+(imm8<<2));desc='addiupc'
  elif op==13:wr(rx,imm8);desc=f'li r{GPR16[rx]}, {imm8}'
  elif op==18:wr(rx,self.read((self.r[29]+(imm8<<2))&U32,4));desc='lwsp'
  elif op==26:self.write((self.r[29]+(imm8<<2))&U32,r(rx),4);desc='swsp'
  elif op==27:self.write((r(ry)+(imm5<<2))&U32,r(rx),4);desc='sw'
  elif op==24:self.write((r(ry)+imm5)&U32,r(rx),1);desc='sb'
  elif op==25:self.write((r(ry)+(imm5<<1))&U32,r(rx),2);desc='sh'
  elif op==16:wr(rx,sign(self.read((r(ry)+imm5)&U32,1),8));desc='lb'
  elif op==17:wr(rx,sign(self.read((r(ry)+(imm5<<1))&U32,2),16));desc='lh'
  elif op==20:wr(rx,self.read((r(ry)+imm5)&U32,1));desc='lbu'
  elif op==6: # SHIFT: ry[10:8], shamt[7:5], rx[4:2], funct[1:0]
   sh=(i>>5)&7;dst=(i>>2)&7;fn=i&3;sh=sh or 8
   if fn==0:wr(dst,r(rx)<<sh)
   elif fn==2:wr(dst,r(rx)>>sh)
   elif fn==3:wr(dst,sign(r(rx),32)>>sh)
   else:raise StopProbe(f'Unsupported MIPS16 SHIFT fn={fn} at 0x{p:08X}')
   desc=f'shift fn={fn} r{GPR16[dst]},r{GPR16[rx]}, {sh}'
  elif op==29: # RR subset
   fn=i&31;kind=fn>>3;sub=fn&7
   if kind==1 and sub in (4,5,6,7):
    a=r(rx);b=r(ry)
    wr(rx, (a&b) if sub==4 else (a|b) if sub==5 else (a^b) if sub==6 else (~a)&U32)
    desc=f'rr logic {kind}:{sub}'
   elif kind==0 and sub==0: # JR/JALR forms; return to caller, treating ISA bit as mode
    if rx==0 and ry==1:target=self.r[31]
    elif ry==0:target=r(rx)
    else:raise StopProbe(f'Unsupported MIPS16 JR form 0x{i:04X} at 0x{p:08X}')
    # JR has a 16-bit delay slot. JRC (ND bit) does not.
    slot=self.read(p+2,2)
    self.log(f'{self.steps:8d} {p:08X} {i:04X} MIPS16 jr -> 0x{target:08X} (delay slot 0x{slot:04X})')
    self.steps+=1
    if not (i&0x80):
     self.step16_delay(p+2,p) # executes arbitrary non-branch 16-bit delay slot
    self.pc=target&~1;self.mode16=bool(target&1)
    self.mode_switches.append((self.steps,p,self.pc,'MIPS16->'+('MIPS16' if self.mode16 else 'MIPS32')))
    self.r[0]=0;return
   else:raise StopProbe(f'Unsupported MIPS16 RR 0x{i:04X} at 0x{p:08X}, kind={kind} sub={sub}')
  elif op==9:wr(rx,r(rx)+sign(imm8,8));desc='addiu8'
  elif op==10:self.r[24]=int(sign(r(rx),32)<sign(imm8,8));desc='slti -> t8'
  elif op==11:self.r[24]=int(r(rx)<imm8);desc='sltiu -> t8'
  elif op==14:self.r[24]=r(rx)^imm8;desc='cmpi -> t8'
  elif op==2:pcnext=(p+2)+(sign(i&0x7ff,11)<<1);desc='b'
  elif op==4:
   if r(rx)==0:pcnext=p+2+(sign(imm8,8)<<1)
   desc='beqz'
  elif op==5:
   if r(rx)!=0:pcnext=p+2+(sign(imm8,8)<<1)
   desc='bnez'
  elif op==12: # I8, branch on T and stack moves
   sub=rx
   if sub==0:
    if self.r[24]==0:pcnext=p+2+(sign(imm8,8)<<1)
    desc='bteqz'
   elif sub==1:
    if self.r[24]!=0:pcnext=p+2+(sign(imm8,8)<<1)
    desc='btnez'
   elif sub==2:self.write((self.r[29]+(imm8<<2))&U32,self.r[31],4);desc='sw ra,offset(sp)'
   elif sub==3:self.r[29]=(self.r[29]+(sign(imm8,8)<<3))&U32;desc='addiu sp,imm*8'
   elif sub==7:wr(ry,self.r[i&31]);desc='move compressed reg,full reg'
   else:raise StopProbe(f'Unsupported MIPS16 I8 0x{i:04X} at 0x{p:08X}')
  else:raise StopProbe(f'Unsupported MIPS16 0x{i:04X} at 0x{p:08X} opcode={op}')
  self.log(f'{self.steps:8d} {p:08X} {i:04X} MIPS16 {desc}')
  self.pc=pcnext&U32;self.r[0]=0;self.steps+=1
 def run(self,limit):
  try:
   while self.steps<limit:
    if self.mode16:self.step16()
    else:self.step32()
  except StopProbe as exc:self.status=str(exc)
  return self.status
 def report(self):
  return {'status':self.status,'instructions':self.steps,'pc':f'0x{self.pc:08X}','mode':'MIPS16' if self.mode16 else 'MIPS32',
   'mips16_instructions':self.mips16_count,'unique_32_pc':len(self.unique32),'unique_16_pc':len(self.unique16),
   'max_ram_offset_written':f'0x{self.max_ram_write:X}',
   'mode_switches':[{'step':s,'from':f'0x{p:08X}','to':f'0x{t:08X}','transition':kind} for s,p,t,kind in self.mode_switches],
   'first_mmio':[{'step':s,'kind':kind,'address':f'0x{a:08X}','bytes':n,'value':f'0x{v:08X}'} for s,kind,a,n,v in self.mmio_first[:60]],
   'pc16_sample':[{'pc':f'0x{p:08X}','word':f'0x{i:04X}'} for p,i in self.pc16_sample],
   'regs':[f'0x{v:08X}' for v in self.r], 'cp0':{str(k):f'0x{v:08X}' for k,v in self.cp0.items()},
   'trace':self.events}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('firmware');ap.add_argument('--steps',type=int,default=4000000);ap.add_argument('--out',default='probe_result.json');ap.add_argument('--unsafe-zero-mmio',action='store_true',help='Continue after unknown peripheral reads using zero; NOT a valid emulation result');args=ap.parse_args()
 flash=get_flash(args.firmware)
 assert len(flash)==2097152,'Expected a 2 MiB FLASH_U202 image'
 p=Probe(flash,unsafe_zero_mmio=args.unsafe_zero_mmio);p.run(args.steps);report=p.report();pathlib.Path(args.out).write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(f"Executed {p.steps:,} | {report['status']} | PC {report['pc']} | {report['mode']} | MIPS16 {p.mips16_count}")
 print('Report:',args.out)
if __name__=='__main__':main()
