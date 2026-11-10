"""Observed on-chip serial TX completion; no external response bytes supplied.

Application2D4C0 writes TX50 and enables IRQ70 bit2, ISR2CCA0 reads/clears
status60 and releases STXD0. Native IRQ table maps it to EMMA mask10000.
Byte latency64 instructions is provisional, not a baud-accurate UART model.
"""
from pace_probe_graphics import GraphicsProbe
from pace_probe import StopProbe

class NativeSerialProbe(GraphicsProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.serial0_enabled=False;self.serial0_regs={a:0 for a in range(0xb2002000,0xb2002080,16)}
        self.serial0_due=None;self.serial0_tx=bytearray();self.serial0_completions=0;self.serial0_acks=0
    def attach_pending_serial0(self):
        for address in self.serial0_regs:
            stream=self.mmio_streams.get((address,4))
            if stream:self.serial0_regs[address]=stream[-1]
        if self.serial0_regs[0xb2002070]&2 and self.mmio_streams.get((0xb2002050,4)):
            self.serial0_tx.append(self.serial0_regs[0xb2002050]&255);self.serial0_due=self.steps+64
        else:raise StopProbe('No queued native serial TX to resume')
    def skip_idle(self,limit):
        if self.serial0_due is not None:return False
        return super().skip_idle(limit)
    def sync_irq(self):
        super().sync_irq()
        if getattr(self,'serial0_enabled',False) and self.serial0_regs[0xb2002060]&self.serial0_regs[0xb2002070]:
            self.read_overrides[0xb0000030]|=0x10000
            if self.timer_regs[0xb0000040]&0x10000:self.cp0[13]|=0x400
    def write(self,address,value,size=4):
        result=super().write(address,value,size)
        if self.serial0_enabled and address in self.serial0_regs and size==4:
            if address==0xb2002060 and value==0 and self.serial0_regs[address]:self.serial0_acks+=1
            self.serial0_regs[address]=value
            if address==0xb2002050:
                self.serial0_tx.append(value&255);self.serial0_due=self.steps+64
            self.sync_irq()
        return result
    def read(self,address,size=4):
        if self.serial0_enabled and 0xb2002000<=address<0xb2002080:
            if address in (0xb2002050,0xb2002053):raise StopProbe('Native serial RX data not supplied')
            if address not in self.serial0_regs or size!=4:raise StopProbe('Unmodelled native serial access width/lane')
            self.read_overrides[address]=self.serial0_regs[address]
        return super().read(address,size)
    def advance_counter(self,retired):
        super().advance_counter(retired)
        if self.serial0_enabled and self.serial0_due is not None and self.steps>=self.serial0_due:
            self.serial0_due=None;self.serial0_regs[0xb2002060]|=2
            self.serial0_completions+=1;self.sync_irq()
    def report(self):
        r=super().report();r['native_serial0']=dict(enabled=self.serial0_enabled,tx=self.serial0_tx.hex(),
            completions=self.serial0_completions,acks=self.serial0_acks,
            due=self.serial0_due,receive_data_supplied=False,byte_delay_instructions=64)
        return r
