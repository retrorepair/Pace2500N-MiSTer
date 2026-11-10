"""Resume trusted local probe snapshot with the new inferred demux model."""
import gzip,pickle,json,argparse
from pathlib import Path
from pace_probe_demux import DemuxProbe
ap=argparse.ArgumentParser();ap.add_argument('--steps',type=int,default=3400000)
ap.add_argument('--snapshot',default='re/demux_configured_snapshot.pkl.gz')
ap.add_argument('--out',default='re/demux_resume_01');a=ap.parse_args()
with gzip.open(a.snapshot,'rb') as f:old=pickle.load(f)
p=DemuxProbe(old.flash);p.__dict__.update(old.__dict__)
p.stop_before_dma=False;p.status='step limit'
if not p.dma_transfers:p.start_dma()
p.run(a.steps)
Path(a.out+'.json').write_text(json.dumps(p.report(),indent=2)+'\n')
Path(a.out+'_ram.bin').write_bytes(p.ram)
with gzip.open(a.out+'.pkl.gz','wb') as f:pickle.dump(p,f)
print(p.steps,p.status,f'PC {p.pc:08X}',p.test_returns,
      'flag',p.ram[0x81f8:0x81fc].hex(),p.demux_outputs)
