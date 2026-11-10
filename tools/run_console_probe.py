import argparse,gzip,pickle,json
from pathlib import Path
from pace_probe_console import ConsoleProbe
ap=argparse.ArgumentParser();ap.add_argument('--steps',type=int,default=18000000);a=ap.parse_args()
with gzip.open('re/serial_completion_extended.pkl.gz','rb') as f:old=pickle.load(f)
p=ConsoleProbe(old.flash);p.__dict__.update(old.__dict__)
p.status='step limit';p.fast_idle=True;p.attach_current_request();p.run(a.steps)
stem='re/console_boot_01'
Path(stem+'.json').write_text(json.dumps(p.report(),indent=2)+'\n')
Path(stem+'.txt').write_bytes(p.uart_tx)
Path(stem+'_ram.bin').write_bytes(p.ram)
with gzip.open(stem+'.pkl.gz','wb') as f:pickle.dump(p,f)
print(p.steps,p.status,f'PC {p.pc:08X}',repr(p.uart_tx.decode('latin1')))
