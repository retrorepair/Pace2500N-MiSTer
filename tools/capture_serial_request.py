import gzip,pickle,json
import argparse
from pathlib import Path
from pace_probe_serial_peer import SerialPeerProbe
ap=argparse.ArgumentParser();ap.add_argument('--requests',type=int,default=1);a=ap.parse_args()
with gzip.open('re/demux_nor_03.pkl.gz','rb') as f:old=pickle.load(f)
p=SerialPeerProbe(old.flash);p.__dict__.update(old.__dict__)
p.status='step limit';p.stop_after_requests=a.requests;p.attach_current_request();p.run(6200000)
Path(f're/serial_peer_capture_{a.requests:02}.json').write_text(json.dumps(p.report(),indent=2)+'\n')
print(p.steps,p.status,p.report()['exploratory_serial_peer'])
