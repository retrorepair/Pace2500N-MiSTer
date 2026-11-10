"""Independent literal-address regressions, MIPS MD00076 table 3-14."""
from pace_probe import Probe

def probe(halfwords, pc=0xbfc00100):
    image=bytearray(2097152)
    for address,code in halfwords.items():
        image[address:address+2]=code.to_bytes(2,'big')
    image[0x140:0x148]=bytes.fromhex('11223344deadbeef')
    result=Probe(bytes(image))
    result.pc=pc
    result.mode16=True
    result.r[31]=0xbfc00008
    return result

p=probe({0x100:0x0a01})
p.step16()
assert p.r[2]==0xbfc00104
p=probe({0x102:0xb310},0xbfc00102)
p.step16()
assert p.r[3]==0x11223344
for instruction,register,value in ((0x0a01,2,0xbfc00104),(0xb310,3,0x11223344)):
    p=probe({0x102:0xe820,0x104:instruction},0xbfc00102)
    p.step16()
    assert p.r[register]==value and p.pc==0xbfc00008 and not p.mode16
for address in (0x100,0x102):
    p=probe({address:0x1a1f,address+2:0x0060,address+4:0x0a01},0xbfc00000+address)
    p.step16()
    assert p.r[2]==0xbfc00104 and p.pc==0xbfc00180 and p.mode16
print('PASS: Python MIPS16 PC bases, normal and JR/JAL delay slots')
