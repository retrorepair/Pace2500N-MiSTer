"""Reset-to-boot verification of inferred peripheral completion replies."""
import json,gzip,pickle
from pathlib import Path
from pace_probe_serial_ack import AckSerialProbe
from pace_probe import get_flash
p=AckSerialProbe(get_flash('firmware/FLASH_U202.bin'),unsafe_zero_mmio=True,counter_ticks=8)
p.run(6500000)
stem='re/serial_completion_fresh_01'
Path(stem+'.json').write_text(json.dumps(p.report(),indent=2)+'\n')
Path(stem+'_ram.bin').write_bytes(p.ram)
with gzip.open(stem+'.pkl.gz','wb') as f:pickle.dump(p,f)
print(p.steps,p.status,p.peer_requests,p.reply_milestones)
