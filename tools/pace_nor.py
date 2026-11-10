"""Read/ID subset of two16-bit NOR profiles in the firmware's table.

Physical chip identification and alias decode are inferred, not measured.
Program/erase commands deliberately stop until their semantics are modelled.
"""
from pace_probe import StopProbe
class NorBank:
    def __init__(self,data,profile='MBM29LV160B'):
        assert profile in ('MBM29LV160B','AT49LV1614')
        self.profile=profile
        self.data=bytes(data);self.unlock=0;self.identify=False;self.commands=[]
    def write(self,address,value,size):
        if size!=2 or address&1:raise StopProbe('Unsupported NOR write width/alignment')
        self.commands.append(dict(offset=f'{address:06X}',value=f'{value:04X}'))
        if value==0xf0:self.identify=False;self.unlock=0;return
        if self.unlock==0 and address==0xaaaa and value==0xaa:self.unlock=1;return
        if self.unlock==1 and address==0x5554 and value==0x55:self.unlock=2;return
        if self.unlock==2 and address==0xaaaa and value==0x90:
            self.identify=True;self.unlock=0;return
        raise StopProbe(f'Unmodelled NOR command {address:06X}={value:04X}')
    def read(self,address,size):
        if address+size>len(self.data):raise StopProbe('NOR read outside bank')
        if not self.identify:return int.from_bytes(self.data[address:address+size],'big')
        # Original tables:2249/0004 at1ADC8;00C0/001F at1AE10.
        # Colibri's board drawing names AT49LV1614; keep the earlier profile
        # available for reproducibility of already recorded experiments.
        ids=bytes.fromhex('001f00c00000' if getattr(self,'profile','MBM29LV160B')=='AT49LV1614' else '000422490000')
        if address+size<=len(ids):return int.from_bytes(ids[address:address+size],'big')
        raise StopProbe(f'Unmodelled NOR identify address {address:06X}')
