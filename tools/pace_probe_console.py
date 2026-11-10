"""Polling16550-style console UART inferred from U202's register accesses.

TX empties immediately; no baud/IRQ timing is claimed. LSR THRE/TEMT bits and
DLAB semantics follow conventional16550 behavior. Register stride is16 bytes.
"""
from collections import deque
from pace_probe_serial_ack import AckSerialProbe
from pace_probe import StopProbe

class ConsoleProbe(AckSerialProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.uart_regs=[0]*8;self.uart_divisor=[0,0]
        self.uart_rx=deque();self.uart_tx=bytearray()
    @staticmethod
    def console_register(address,size):
        if not 0xb2001000<=address<0xb2001080:return None
        index=(address-0xb2001000)//16;lane=address&15
        if (size==4 and lane==0) or (size==1 and lane==3):return index
        raise StopProbe('Unsupported console UART access lane/width')
    def write(self,address,value,size=4):
        index=self.console_register(address,size)
        super().write(address,value,size)
        if index is None:return
        value&=255
        if index in (0,1) and self.uart_regs[3]&0x80:self.uart_divisor[index]=value
        elif index==0:self.uart_tx.append(value)
        else:
            self.uart_regs[index]=value
            if index==2 and value&2:self.uart_rx.clear()
    def read(self,address,size=4):
        index=self.console_register(address,size)
        if index is not None:
            if index in (0,1) and self.uart_regs[3]&0x80:value=self.uart_divisor[index]
            elif index==0:value=self.uart_rx.popleft() if self.uart_rx else 0
            elif index==5:value=0x60|int(bool(self.uart_rx))
            elif index==2:value=1 # no UART interrupt currently pending
            else:value=self.uart_regs[index]
            self.read_overrides[address]=value
        return super().read(address,size)
    def report(self):
        r=super().report();r['genuine_console_output']=self.uart_tx.decode('latin1')
        return r
