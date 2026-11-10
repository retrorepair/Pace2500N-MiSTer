import argparse,gzip,pickle,json
from pathlib import Path
from pace_probe_serial_ack import AckSerialProbe
ap=argparse.ArgumentParser();ap.add_argument('--wrong-sequence',action='store_true');ap.add_argument('--sync-ack-only',action='store_true');ap.add_argument('--steps',type=int,default=6500000);ap.add_argument('--snapshot',default='re/demux_nor_03.pkl.gz');ap.add_argument('--out');ap.add_argument('--fast-idle',action='store_true');a=ap.parse_args()
with gzip.open(a.snapshot,'rb') as f:old=pickle.load(f)
p=AckSerialProbe(old.flash,wrong_sequence=a.wrong_sequence,sync_ack_only=a.sync_ack_only);p.__dict__.update(old.__dict__)
p.status='step limit';p.fast_idle=a.fast_idle;p.attach_current_request();p.run(a.steps)
stem=a.out or ('re/serial_sync_ack_only' if a.sync_ack_only else ('re/serial_sync_wrongseq' if a.wrong_sequence else 're/serial_sync_completion'))
Path(stem+'.json').write_text(json.dumps(p.report(),indent=2)+'\n')
Path(stem+'_ram.bin').write_bytes(p.ram)
with gzip.open(stem+'.pkl.gz','wb') as f:pickle.dump(p,f)
print(p.steps,p.status,p.peer_requests,p.replies[-8:])
