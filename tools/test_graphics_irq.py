"""Replay a real queued command and let the original DMA ISR acknowledge it."""
import gzip,pickle
from pace_probe_graphics import GraphicsProbe
old=pickle.load(gzip.open('re/application_uart_01.pkl.gz','rb'))
p=GraphicsProbe(old.flash);p.__dict__.update(old.__dict__)
assert p.demux_regs[0xb0009010]&0x1000
p.start_graphics_dma();assert p.graphics_dma_pending==0x1000
assert p.read_overrides[0xb0000030]&2
p.run(p.steps+50000)
assert p.status=='step limit',p.status
assert p.graphics_dma_completions==2 and p.graphics_dma_acks==2
assert p.graphics_dma_pending==0
assert [e['color'] for e in p.graphics_events]==['1010','8080']
assert all(p.ram[int(e['start'],16):int(e['end'],16)]==bytes.fromhex(e['color'])*((int(e['end'],16)-int(e['start'],16))//2) for e in p.graphics_events)
print('PASS: original DMA IRQ mask2 handler acknowledges both luma/chroma commands and guest proceeds')
