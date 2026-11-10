#!/usr/bin/env python3
"""Research-only synthetic Count/Compare time and architected interrupts.

Counter ticks per retired guest instruction are an explicit approximation,
not measured VR4110/EMMA cycle timing. Unknown hardware still requires explicit
experimental MMIO policy. NEC VR41xx manual sections 6.2.3/6.2.4 define the
free-running Count, Compare match IP7, and Compare-write acknowledgement.
"""
import argparse
import json
from pathlib import Path
from pace_probe import StopProbe, U32, get_flash
from pace_probe_research import ResearchProbe


class TimedProbe(ResearchProbe):
    def __init__(self,*args,counter_ticks=1,fast_idle=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.counter_ticks=counter_ticks
        self.timer_armed=False
        self.interrupt_count=0
        self.interrupt_events=[]
        self.compare_writes=0
        self.delay_origin=None
        self.fast_idle=fast_idle
        self.idle_skipped=0

    def skip_idle(self,limit):
        """Skip whole verified eight-instruction scheduler loops before IP7.

        No register, MMIO or RAM effects occur in these loops. Keep at least
        one complete loop before Compare so normal interrupt timing handles
        the boundary. This applies only to this exact ROM and idle state.
        """
        if not self.fast_idle or self.mode16 or self.pc!=0x9fc0de4c or self.branch is not None:return False
        if self.delay_origin is not None or not self.timer_armed or self.cp0.get(13,0)&0x8000:return False
        if any(self.ram[0x83d0:0x83d4]) or any(self.ram[0x83fc:0x8400]):return False
        expected=bytes.fromhex('3c0180018c2483fc3c0180018c2883d014800003000000001100fff935040000')
        if self.flash[0xde4c:0xde6c]!=expected:return False
        # At loop entry these are the only registers the idle loop writes.
        if self.r[1]!=0x80010000 or self.r[4]!=0 or self.r[8]!=0:return False
        distance=(self.cp0.get(11,0)-self.cp0.get(9,0))&U32
        loops=min((limit-self.steps)//8,max(0,distance//(8*self.counter_ticks)-1))
        if loops<=0:return False
        retired=loops*8;self.steps+=retired;self.idle_skipped+=retired
        self.advance_counter(retired)
        self.recent.append(f'{self.steps:8d} verified idle fast-forward {retired} instructions')
        return True

    def step32(self):
        instruction=self.read(self.pc,4)
        mtc0=instruction>>26==16 and ((instruction>>21)&31)==4
        register=(instruction>>11)&31
        cause=self.cp0.get(13,0)
        super().step32()
        if mtc0 and register==11:
            self.cp0[13]=self.cp0.get(13,0)&~0x8000
            self.timer_armed=True;self.compare_writes+=1
        elif mtc0 and register==13:
            self.cp0[13]=(cause&~0x300)|(self.cp0.get(13,0)&0x300)

    def advance_counter(self,retired):
        old=self.cp0.get(9,0)
        delta=retired*self.counter_ticks
        self.cp0[9]=(old+delta)&U32
        distance=(self.cp0.get(11,0)-old)&U32
        if self.timer_armed and (delta>=0x100000000 or 0<distance<=delta):
            self.cp0[13]=self.cp0.get(13,0)|0x8000

    def deliver_interrupt(self):
        status=self.cp0.get(12,0);cause=self.cp0.get(13,0)
        if not(status&1) or status&6 or not(status&cause&0xff00):return
        epc=self.delay_origin if self.delay_origin is not None else self.pc
        isa=False if self.delay_origin is not None else self.mode16
        self.cp0[14]=(epc&~1)|int(isa)
        self.cp0[13]=(cause&~0x8000007c)|(0x80000000 if self.delay_origin is not None else 0)
        self.cp0[12]=status|2
        vector=0xbfc00380 if status&0x400000 else 0x80000180
        self.interrupt_count+=1
        event={'step':self.steps,'epc':f'{self.cp0[14]:08X}','vector':f'{vector:08X}',
               'cause':f'{self.cp0[13]:08X}','count':f'{self.cp0.get(9,0):08X}'}
        if len(self.interrupt_events)<1000:self.interrupt_events.append(event)
        self.recent.append(f'{self.steps:8d} IRQ {event}')
        self.pc=vector;self.mode16=False;self.branch=None;self.delay_origin=None

    def run(self,limit):
        try:
            while self.steps<limit:
                if self.pc==getattr(self,'stop_before_application_pc',None):
                    raise StopProbe(f'Diagnostic breakpoint before {self.pc:08X}')
                if self.skip_pure_loop(limit):continue
                if self.skip_idle(limit):continue
                pc=self.pc;mode=self.mode16;before=self.steps
                instruction=self.read(pc,2 if mode else 4)
                if mode:self.step16()
                else:self.step32()
                retired=self.steps-before
                # Deferred MIPS32 branches leave their slot as the next PC.
                if not mode and retired==1 and instruction>>26 in (1,2,3,4,5,6,7,20,21,22,23) and self.pc==(pc+4)&U32:
                    self.delay_origin=pc
                else:self.delay_origin=None
                self.advance_counter(retired)
                self.deliver_interrupt()
        except StopProbe as exc:self.status=str(exc)
        return self.status

    def skip_pure_loop(self,limit):return False

    def report(self):
        report=super().report()
        report.update(counter_ticks_per_instruction=self.counter_ticks,
                      synthetic_time=True,interrupt_count=self.interrupt_count,
                      fast_idle=self.fast_idle,idle_instructions_skipped=self.idle_skipped,
                      interrupt_events=self.interrupt_events,compare_writes=self.compare_writes,
                      observed_kernel_tick_8000842c=f'{int.from_bytes(self.ram[0x842c:0x8430],"big"):08X}')
        return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('firmware');ap.add_argument('--steps',type=int,default=10000000)
    ap.add_argument('--counter-ticks',type=int,default=8)
    ap.add_argument('--out',default='timed_probe.json')
    ap.add_argument('--unsafe-zero-mmio',action='store_true')
    ap.add_argument('--experimental-read',action='append',default=[])
    ap.add_argument('--dump-ram',help='Save the final guest RAM bytes for RE')
    ap.add_argument('--fast-idle',action='store_true')
    args=ap.parse_args()
    overrides={int(a,16):int(v,16) for a,v in (item.split('=') for item in args.experimental_read)}
    p=TimedProbe(get_flash(args.firmware),unsafe_zero_mmio=args.unsafe_zero_mmio,
                 read_overrides=overrides,counter_ticks=args.counter_ticks,fast_idle=args.fast_idle)
    p.run(args.steps)
    Path(args.out).write_text(json.dumps(p.report(),indent=2)+'\n')
    if args.dump_ram:Path(args.dump_ram).write_bytes(p.ram)
    print(f'{p.steps:,} instructions | {p.status} | PC {p.pc:08X} | IRQ {p.interrupt_count}')
    print('Report:',args.out)

if __name__=='__main__':main()

