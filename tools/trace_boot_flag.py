"""Observe boot-mode flag writes without changing guest memory or control flow."""
from pathlib import Path
import json
from pace_probe_emma_timer import EmmaTimerProbe
from pace_probe import get_flash

class FlagProbe(EmmaTimerProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.flag_writes=[]
    def write(self,address,value,size=4):
        address&=0xffffffff
        if address<=0x800081fb and address+size>0x800081f8:
            self.flag_writes.append(dict(step=self.steps,pc=f'{self.pc:08X}',address=f'{address:08X}',
                size=size,value=f'{value&((1<<(8*size))-1):0{size*2}X}',
                registers=[f'{v:08X}' for v in self.r],trace=list(self.recent)[-24:]))
        return super().write(address,value,size)

if __name__=='__main__':
    p=FlagProbe(get_flash('firmware/FLASH_U202.bin'),unsafe_zero_mmio=True,
        read_overrides={0xb0009120:0x20},counter_ticks=8)
    p.run(3600000)
    Path('re/boot_flag_writes.json').write_text(json.dumps(p.flag_writes,indent=2)+'\n')
    print('Flag writes:',[(x['step'],x['pc'],x['value']) for x in p.flag_writes])
