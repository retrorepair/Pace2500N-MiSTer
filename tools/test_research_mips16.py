"""Directed encodings cross-checked with MIPS MD00076 / Ghidra."""
from pace_probe_research import ResearchProbe

def probe(words,pc=0xbfc00100):
    image=bytearray(2097152)
    for j,word in enumerate(words):image[0x100+j*2:0x102+j*2]=word.to_bytes(2,'big')
    p=ResearchProbe(bytes(image));p.pc=pc;p.mode16=True
    return p

# SW/LW: rx is the base, ry is the stored/loaded register; distinct values.
p=probe([0xdf60,0x9f40]);p.r[7]=0x80000000;p.r[3]=0x11223344
p.step16();assert p.ram[:4]==bytes.fromhex('11223344')
p.step16();assert p.r[2]==0x11223344
# EXTEND SW with the real first unsupported pair, at a halfword boundary too.
p=probe([0x6c00,0xf140,0xdf60],0xbfc00102);p.r[7]=0x80000000;p.r[3]=0x55667788
p.step16();assert p.ram[0x140:0x144]==bytes.fromhex('55667788') and p.pc==0xbfc00106
# SLL v0,v1,5: destination rx, source ry, shift bits 4:2.
p=probe([0x3274]);p.r[3]=3;p.step16();assert p.r[2]==96 and p.r[3]==3
# Real EXTEND shift pair: SLL a2,a2,16.
p=probe([0xf400,0x36c0]);p.r[6]=0x1234;p.step16();assert p.r[6]==0x12340000 and p.pc==0xbfc00104
# NOT v0,v1 uses the source register, not the old destination.
p=probe([0xea6f]);p.r[2]=1;p.r[3]=0xf0;p.step16();assert p.r[2]==0xffffff0f
# Compact return skips the following instruction and switches ISA from RA.
p=probe([0xe8a0,0x6a55]);p.r[31]=0xbfc00200;p.step16()
assert p.pc==0xbfc00200 and not p.mode16 and p.r[2]==0 and p.steps==1
# Extended LI is unsigned 16-bit, even for FFFF.
p=probe([0xf7ff,0x6a1f]);p.step16();assert p.r[2]==0xffff
print('PASS: research MIPS16 register roles, EXTEND, shifts, NOT and compact return')
