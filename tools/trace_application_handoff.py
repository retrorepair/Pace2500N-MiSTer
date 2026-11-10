"""Read-only execution trace of selected-image handoff; never redirects the PC."""
import argparse,gzip,pickle,json
from pathlib import Path
from pace_probe_boot_peripheral import BootPeripheralProbe
from pace_probe import StopProbe

class HandoffTrace(BootPeripheralProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.handoff_trace=[];self.handoff_writes=[];self.handoff_active=False
    def step16(self):
        if self.pc in (0x9fc12614,0xbfc12614):self.handoff_active=True
        if self.handoff_active:
            self.handoff_trace.append(dict(step=self.steps,pc=f'{self.pc:08X}',
                instruction=f'{self.read(self.pc,2):04X}',gpr=[f'{n:08X}' for n in self.r]))
            if self.pc in (0x9fc036f8,0xbfc036f8):
                raise StopProbe('Selected-image routine returned into permanent wait')
        return super().step16()
    def write(self,address,value,size=4):
        if self.handoff_active:self.handoff_writes.append(dict(step=self.steps,pc=f'{self.pc:08X}',address=f'{address:08X}',size=size,value=f'{value:08X}'))
        return super().write(address,value,size)

if __name__=='__main__':
    # Use the importable class in snapshots, not an unportable __main__ class.
    from trace_application_handoff import HandoffTrace
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',default='re/peripheral_boot_01.pkl.gz');ap.add_argument('--out',default='re/handoff_execution');ap.add_argument('--steps',type=int,default=65000000);a=ap.parse_args()
    with gzip.open(a.snapshot,'rb') as f:old=pickle.load(f)
    p=HandoffTrace(old.flash);p.__dict__.update(old.__dict__)
    p.fast_crc=True;p.fast_idle=True;p.run(a.steps)
    report=dict(status=p.status,steps=p.steps,pc=f'{p.pc:08X}',trace=p.handoff_trace,writes=p.handoff_writes,
        selected_header=p.ram[0x2000:0x2020].hex(),application_entries=p.application_entries,
        console=p.uart_tx.decode('latin1'),flash_unchanged=p.flash==Path('firmware/FLASH_U202.bin').read_bytes())
    Path(a.out+'.json').write_text(json.dumps(report,indent=2)+'\n')
    with gzip.open(a.out+'.pkl.gz','wb') as f:pickle.dump(p,f)
    print(p.status,p.steps,f'{p.pc:08X}',len(p.handoff_trace),'instructions traced',len(p.handoff_writes),'writes')
