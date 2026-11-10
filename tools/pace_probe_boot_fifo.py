"""Research-only data-port loopback inferred from U202's first self-test.

The second B000Axxx test is deliberately left unimplemented. Never force its
success values, boot-mode flag, semaphore state or control flow.
"""
from collections import deque
from pathlib import Path
import json
from trace_boot_flag import FlagProbe
from pace_probe import get_flash,StopProbe

class BootFifoProbe(FlagProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fifo=deque();self.fifo_mode=0;self.fifo_writes=0;self.fifo_reads=0
        self.test_returns={}
    def write(self,address,value,size=4):
        super().write(address,value,size)
        if size!=4:return
        if address==0xb00020b4:
            if value==1 and self.fifo_mode!=1:self.fifo.clear()
            self.fifo_mode=value
        elif address==0xb00020b0 and self.fifo_mode==1:
            self.fifo.append(value&0xffffffff);self.fifo_writes+=1
    def read(self,address,size=4):
        if address==0xb00020b8 and size==4:self.read_overrides[address]=0
        if address==0xb00020b0 and size==4 and self.fifo_mode==2:
            if not self.fifo:raise StopProbe(f'Unmodelled empty FIFO read PC={self.pc:08X}')
            self.read_overrides[address]=self.fifo.popleft();self.fifo_reads+=1
        return super().read(address,size)
    def step16(self):
        if self.pc in (0xbfc0b456,0xbfc0b45c):
            self.test_returns[f'{self.pc:08X}']=f'{self.r[2]:08X}'
        return super().step16()

if __name__=='__main__':
    p=BootFifoProbe(get_flash('firmware/FLASH_U202.bin'),unsafe_zero_mmio=True,
        read_overrides={0xb0009120:0x20},counter_ticks=8)
    p.run(3300000)
    r=p.report();r.update(fifo_writes=p.fifo_writes,fifo_reads=p.fifo_reads,
        self_test_returns=p.test_returns,boot_flag_writes=p.flag_writes)
    Path('re/boot_fifo_01.json').write_text(json.dumps(r,indent=2)+'\n')
    print(p.status,p.steps,f'PC {p.pc:08X}',p.fifo_writes,p.fifo_reads,p.test_returns)
