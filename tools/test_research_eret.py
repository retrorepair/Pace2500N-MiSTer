"""ERET status/ISA tests from NEC VR41xx and MIPS privileged-resource manuals."""
from pace_probe_research import ResearchProbe

for status,epc,error_epc,expected_status,target in [
    (2,0xbfc00200,0xbfc00401,0,0xbfc00200),
    (2,0xbfc00201,0xbfc00400,0,0xbfc00201),
    (4,0xbfc00201,0xbfc00400,0,0xbfc00400),
    (6,0xbfc00200,0xbfc00401,2,0xbfc00401),
    (0,0xbfc00201,0xbfc00400,0,0xbfc00201),
]:
    image=bytearray(2097152);image[0x100:0x104]=bytes.fromhex('42000018')
    p=ResearchProbe(bytes(image));p.pc=0xbfc00100;p.mode16=False
    p.cp0.update({12:status,14:epc,30:error_epc});p.llbit=True
    p.step32()
    assert p.pc==target&~1 and p.mode16==bool(target&1)
    assert p.cp0[12]==expected_status and not p.llbit and p.steps==1
print('PASS: ERET selects EPC/ErrorEPC, clears EXL/ERL, restores ISA and clears LLbit')
