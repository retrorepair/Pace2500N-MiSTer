"""Research model of EMMA timer0, inferred from genuine U202 driver code.

No claim of a complete NEC timer specification. Clock ratio and periodic-mode
bit are hypotheses; status/ack addresses and IRQ routing come from Ghidra.
"""
import argparse,json
from pathlib import Path
from pace_probe_timed import TimedProbe
from pace_probe import get_flash

class EmmaTimerProbe(TimedProbe):
    def __init__(self,*args,peripheral_ticks=32,**kwargs):
        super().__init__(*args,**kwargs)
        self.peripheral_ticks=peripheral_ticks
        self.timer_regs={a:0 for a in (0xb0000040,0xb000d020,0xb000d030,0xb000d050,0xb000d0c0)}
        self.timer_remaining=0;self.timer_pending=False
        self.expirations=0;self.acknowledgements=0
        self.boot_calls=[];self.milestones={}

    def call_snapshot(self,source,target,kind):
        super().call_snapshot(source,target,kind)
        offset=source&0x1fffff
        if 0x1290<=offset<0x132e or 0x5400<=offset<0x5700 or 0x6914<=offset<0x6a1a:
            if len(self.boot_calls)<2048:self.boot_calls.append(self.calls[-1])

    def step16(self):
        if self.pc in (0x9fc069f6,0x9fc069fc,0x9fc0563c,0x9fc012ce,0x9fc012e6,0x9fc2048c):
            self.milestones.setdefault(f'{self.pc:08X}',dict(step=self.steps,v0=f'{self.r[2]:08X}',sp=f'{self.r[29]:08X}'))
        return super().step16()

    def sync_irq(self):
        asserted=self.timer_pending and self.timer_regs[0xb000d0c0]&1
        self.read_overrides[0xb0000030]=0x40 if asserted else 0
        self.read_overrides[0xb000d0d0]=int(self.timer_pending)
        for a,v in self.timer_regs.items():self.read_overrides[a]=v
        cause=self.cp0.get(13,0)&~0x400
        self.cp0[13]=cause|(0x400 if asserted and self.timer_regs[0xb0000040]&0x40 else 0)

    def read(self,address,size=4):
        if address in self.timer_regs or address in (0xb0000030,0xb000d0d0):self.sync_irq()
        return super().read(address,size)

    def write(self,address,value,size=4):
        super().write(address,value,size)
        if size!=4:return
        if address in self.timer_regs:
            old=self.timer_regs[address];self.timer_regs[address]=value&0xffffffff
            if address==0xb000d030 and value&1 and not old&1:
                self.timer_remaining=self.timer_regs[0xb000d050]
        if address==0xb000d0e0 and value&1:
            self.timer_pending=False;self.acknowledgements+=1
        self.sync_irq()

    def advance_counter(self,retired):
        super().advance_counter(retired)
        if self.timer_regs[0xb000d030]&1 and self.timer_regs[0xb000d050]>0:
            self.timer_remaining-=retired*self.peripheral_ticks
            if self.timer_remaining<=0:
                reload=self.timer_regs[0xb000d050]
                self.expirations+=1+(-self.timer_remaining)//reload
                self.timer_pending=True
                if self.timer_regs[0xb000d020]&1:
                    self.timer_remaining=reload-((-self.timer_remaining)%reload)
                else:self.timer_regs[0xb000d030]&=~1
        self.sync_irq()

    def skip_idle(self,limit):
        # Bound whole idle-loop skips by both timer deadlines. External serial
        # events must still run normally; dynamic dispatch advances both timers.
        if self.cp0.get(13,0)&0xfc00 or getattr(self,'clock_due',None) is not None:return False
        if self.timer_regs[0xb000d030]&1:
            before_expiry=max(0,(self.timer_remaining-1)//self.peripheral_ticks-8)
            limit=min(limit,self.steps+before_expiry)
        return super().skip_idle(limit)

    def report(self):
        r=super().report()
        r['experimental_emma_timer0']={
            'peripheral_ticks_per_instruction':self.peripheral_ticks,
            'expirations':self.expirations,'acks':self.acknowledgements,
            'pending':self.timer_pending,
            'registers':{f'{a:08X}':f'{v:08X}' for a,v in self.timer_regs.items()}}
        r['boot_task_calls']=self.boot_calls;r['boot_milestones']=self.milestones
        return r

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--steps',type=int,default=8000000)
    ap.add_argument('--out',default='re/emma_timer_probe.json');ap.add_argument('--dump-ram')
    ap.add_argument('--peripheral-ticks',type=int,default=32)
    a=ap.parse_args()
    p=EmmaTimerProbe(get_flash('firmware/FLASH_U202.bin'),unsafe_zero_mmio=True,
        read_overrides={0xb0009120:0x20},counter_ticks=8,peripheral_ticks=a.peripheral_ticks)
    p.run(a.steps)
    Path(a.out).write_text(json.dumps(p.report(),indent=2)+'\n')
    if a.dump_ram:Path(a.dump_ram).write_bytes(p.ram)
    print(p.steps,p.status,f'PC {p.pc:08X}',p.report()['experimental_emma_timer0'])
