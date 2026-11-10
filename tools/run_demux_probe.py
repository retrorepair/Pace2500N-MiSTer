"""Fresh reset-to-boot run of the explicitly inferred device models."""
import argparse,json,gzip,pickle
from pathlib import Path
from pace_probe_demux import DemuxProbe
from pace_probe import get_flash
ap=argparse.ArgumentParser();ap.add_argument('--steps',type=int,default=6000000)
ap.add_argument('--out',default='re/demux_fresh_01');a=ap.parse_args()
p=DemuxProbe(get_flash('firmware/FLASH_U202.bin'),unsafe_zero_mmio=True,counter_ticks=8)
p.run(a.steps)
Path(a.out+'.json').write_text(json.dumps(p.report(),indent=2)+'\n')
Path(a.out+'_ram.bin').write_bytes(p.ram)
with gzip.open(a.out+'.pkl.gz','wb') as f:pickle.dump(p,f)
print(p.steps,p.status,f'PC {p.pc:08X}',p.test_returns,
      'flag',p.ram[0x81f8:0x81fc].hex(),p.demux_outputs)
