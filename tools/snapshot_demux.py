import gzip,pickle,json
from pathlib import Path
from pace_probe_demux import DemuxProbe
from pace_probe import get_flash
p=DemuxProbe(get_flash('firmware/FLASH_U202.bin'),unsafe_zero_mmio=True,
    read_overrides={0xb0009120:0x20},counter_ticks=8)
p.stop_before_dma=True;p.run(3400000)
with gzip.open('re/demux_configured_snapshot.pkl.gz','wb') as f:pickle.dump(p,f)
r=dict(status=p.status,pc=f'{p.pc:08X}',steps=p.steps,
    banks={f'{port:03X}':{f'{k:03X}':f'{v:08X}' for k,v in b.items()} for port,b in p.demux_banks.items()},
    registers={f'{k:X}':f'{v:08X}' for k,v in p.demux_regs.items()},dma_events=p.dma_events)
Path('re/demux_configured_snapshot.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
