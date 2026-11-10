import argparse,gzip,pickle,json
from pathlib import Path
from pace_probe_boot_peripheral import BootPeripheralProbe
ap=argparse.ArgumentParser();ap.add_argument('--steps',type=int,default=30000000);ap.add_argument('--snapshot',default='re/serial_completion_extended.pkl.gz');ap.add_argument('--out',default='re/peripheral_boot_01');ap.add_argument('--fast-crc',action='store_true');a=ap.parse_args()
with gzip.open(a.snapshot,'rb') as f:old=pickle.load(f)
p=BootPeripheralProbe(old.flash);p.__dict__.update(old.__dict__)
p.status='step limit';p.fast_idle=True;p.fast_crc=a.fast_crc;p.attach_current_request();p.run(a.steps)
stem=a.out
Path(stem+'.json').write_text(json.dumps(p.report(),indent=2)+'\n')
Path(stem+'.txt').write_bytes(p.uart_tx)
Path(stem+'_ram.bin').write_bytes(p.ram)
with gzip.open(stem+'.pkl.gz','wb') as f:pickle.dump(p,f)
print(p.steps,p.status,f'PC {p.pc:08X}',repr(p.uart_tx.decode('latin1')),'APP',p.application_entries)
