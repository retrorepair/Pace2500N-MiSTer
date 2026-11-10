"""External16550 polling subset. Guest byte lanes are reversed within32 bits.

Derived from UARTMRAc/UARTMWAc driver, FIFO87, MCR0D and divisor accesses.
No IRQ source or modem command responses are supplied yet. TX empties instantly.
"""
from collections import deque
class ExternalUart:
    def __init__(self):
        self.regs=[0]*8;self.divisor=[0,0];self.rx=deque();self.tx=bytearray();self.accesses=[]
    def read(self,offset):
        reg=offset^3
        if reg in (0,1) and self.regs[3]&128:return self.divisor[reg]
        if reg==0:return self.rx.popleft() if self.rx else 0
        if reg==2:return 1
        if reg==5:return 0x60|int(bool(self.rx))
        if reg==6:return 0 # no carrier/CTS/DSR asserted
        return self.regs[reg]
    def write(self,offset,value):
        reg=offset^3;value&=255;self.accesses.append(dict(register=reg,value=f'{value:02X}'))
        if reg in (0,1) and self.regs[3]&128:self.divisor[reg]=value
        elif reg==0:self.tx.append(value)
        elif reg==2:
            if value&2:self.rx.clear()
        else:self.regs[reg]=value
    def report(self):
        return dict(profile='16550 polling; guest byte address XOR3',registers=self.regs,
            divisor=self.divisor,tx=self.tx.hex(),text=self.tx.decode('latin1'),
            irq_modelled=False,modem_response_supplied=False,writes=self.accesses)
