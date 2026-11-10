"""Diagnostic A0/A1 EEPROM with observed two-byte big-endian addressing.

No original EEPROM dump is available. This optional profile starts erased (FF),
retains only guest writes, and assumes a64KiB address space and instant writes.
Capacity/page-wrap/write-cycle timing are not identified for the real board.
"""
import hashlib
from pace_probe import StopProbe

class BlankEeprom16:
    def __init__(self):
        self.data=bytearray([255])*65536;self.pointer=0;self.address_bytes=[]
        self.pending=[];self.reading=False;self.read_count=0;self.write_count=0
    def begin(self,address):
        if address not in (0xa0,0xa1):raise StopProbe('Unsupported EEPROM slave')
        self.reading=bool(address&1);self.address_bytes=[]
    def write(self,value):
        if self.reading:raise StopProbe('Write payload during EEPROM read')
        if len(self.address_bytes)<2:
            self.address_bytes.append(value)
            if len(self.address_bytes)==2:self.pointer=int.from_bytes(bytes(self.address_bytes),'big')
        else:
            self.pending.append((self.pointer,value));self.pointer=(self.pointer+1)&65535
    def stop(self):
        for address,value in self.pending:self.data[address]=value
        self.write_count+=len(self.pending);self.pending=[]
    def read(self):
        if not self.reading:raise StopProbe('EEPROM read before read address')
        value=self.data[self.pointer];self.pointer=(self.pointer+1)&65535;self.read_count+=1
        return value
    def report(self):
        return dict(profile='diagnostic erased EEPROM, no original dump',capacity=65536,
            address_bytes=2,initial_byte='FF',pointer=f'{self.pointer:04X}',reads=self.read_count,
            writes=self.write_count,sha256=hashlib.sha256(self.data).hexdigest(),
            timing='instant writes; page wrap unmodelled')
