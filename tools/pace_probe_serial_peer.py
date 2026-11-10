"""Exploratory serial-clock peer: capture requests, never invent responses.

Hypothesis: GPIO0 falling edge requests one full-duplex byte. The firmware's
ISR reads RX at B2009010, clears B2009020 bit0, and receives EMMA IRQ bit13.
"""
from pace_probe_demux import DemuxProbe
from pace_probe import StopProbe

class SerialPeerProbe(DemuxProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.serial_regs={a:0 for a in range(0xb2009000,0xb2009040,16)}
        self.gpio_regs={};self.serial_rx=0;self.clock_due=None
        self.wire_tx=[];self.peer_body=bytearray();self.peer_escape=False;self.peer_requests=[]
        self.stop_after_requests=1

    def attach_current_request(self):
        # Reconstruct register values when resuming an older trusted snapshot.
        for event in self.recent_mmio:
            if event['kind']!='write':continue
            address=int(event['address'],16);value=int(event['value'],16)
            if address in self.serial_regs:self.serial_regs[address]=value
            if 0xb200a000<=address<0xb200a100:self.gpio_regs[address]=value
        if self.serial_regs[0xb2009000]&0x80 and not self.gpio_regs.get(0xb200a000,0)&1:
            self.clock_due=self.steps+64

    def sync_irq(self):
        super().sync_irq()
        if not hasattr(self,'serial_regs'):return
        pending=bool(self.serial_regs[0xb2009020]&1 and self.serial_regs[0xb2009030]&1)
        if pending:
            self.read_overrides[0xb0000030]|=0x2000
            if self.timer_regs[0xb0000040]&0x2000:self.cp0[13]|=0x400

    def write(self,address,value,size=4):
        old=self.gpio_regs.get(address,0) if hasattr(self,'gpio_regs') else 0
        super().write(address,value,size)
        if size!=4:return
        if address in self.serial_regs:self.serial_regs[address]=value&0xffffffff
        if 0xb200a000<=address<0xb200a100:self.gpio_regs[address]=value&0xffffffff
        if address==0xb200a000 and old&1 and not value&1 and self.serial_regs[0xb2009000]&0x80:
            self.clock_due=self.steps+64
        self.sync_irq()

    def read(self,address,size=4):
        if address in self.serial_regs:
            self.read_overrides[address]=self.serial_rx if address==0xb2009010 else self.serial_regs[address]
        elif address in self.gpio_regs:self.read_overrides[address]=self.gpio_regs[address]
        return super().read(address,size)

    def advance_counter(self,retired):
        super().advance_counter(retired)
        if self.clock_due is not None and self.steps>=self.clock_due:
            self.clock_due=None
            incoming=self.peer_rx_byte()
            byte=self.serial_regs[0xb2009010]&255;self.wire_tx.append(byte)
            if self.peer_escape:self.peer_body.append(byte);self.peer_escape=False
            elif byte==0x1b:self.peer_escape=True
            elif byte:self.peer_body.append(byte)
            elif self.peer_body:
                body=bytes(self.peer_body);self.peer_body.clear();self.handle_request(body)
            self.serial_rx=incoming;self.serial_regs[0xb2009020]|=1;self.sync_irq()

    def peer_rx_byte(self):return 0

    def handle_request(self,body):
        self.peer_requests.append(body.hex())
        if len(self.peer_requests)>=self.stop_after_requests:
            raise StopProbe('Captured serial peer request; response semantics unmodelled')

    def report(self):
        r=super().report()
        r['exploratory_serial_peer']=dict(clock_hypothesis='GPIO0 falling requests a byte',
            tx_wire=bytes(self.wire_tx).hex(),requests=self.peer_requests,partial=self.peer_body.hex())
        return r
