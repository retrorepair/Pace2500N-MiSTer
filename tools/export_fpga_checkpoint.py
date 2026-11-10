"""Export the disclosed Guide diagnostic state for FPGA-only CPU resume."""
import sys,gzip,pickle,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with gzip.open(ROOT/'re/application_guide_ramgates_03.pkl.gz','rb') as f:p=pickle.load(f)
assert p.branch is None and p.delay_origin is None
assert p.clock_due is None and p.i2c_due is None and p.serial0_due is None
assert not p.rx_wire and not p.graphics_dma_pending
out=ROOT/'re/fpga_guide_checkpoint';out.mkdir(exist_ok=True)
(out/'RAM.bin').write_bytes(p.ram)
state=list(p.r)+[p.cp0.get(i,0) for i in range(32)]+[p.pc,int(p.mode16)|(int(p.timer_armed)<<1),p.hi,p.lo,p.steps]
(out/'STATE.bin').write_bytes(b''.join(v.to_bytes(4,'big') for v in state))
with (out/'ram64.hex').open('w') as f:
    for a in range(0,len(p.ram),8):f.write(p.ram[a:a+8][::-1].hex()+'\n')
(ROOT/'rom/checkpoint_cpu.hex').write_text(''.join(f'{v:08x}\n' for v in state))
(ROOT/'rom/checkpoint_eeprom.hex').write_text(''.join(f'{v:02x}\n' for v in p.eeprom.data))
(ROOT/'rom/checkpoint_lsi4.hex').write_text(''.join(f'{p.lsi_grouped.groups[4].get(i,0):02x}\n' for i in range(128)))
regs={}
for k in ['timer_regs','serial_regs','gpio_regs','i2c_regs','serial0_regs']:regs.update(getattr(p,k))
readset={a for (kind,a,size) in p.mmio if kind=='read' and size==4}
readset.update([0xb0009010,0xb0009100,0xb000603c,0xb0004200])
for (a,size),values in p.mmio_streams.items():
    if size==4 and a in readset and a not in regs:regs[a]=values[-1]
for a in readset:
    if a not in regs:regs[a]=p.read_overrides.get(a,0)
regs.update({0xb0009010:p.demux_regs.get(0xb0009010,0),0xb0009100:p.demux_regs.get(0xb0009100,0)})
items=sorted(regs.items());assert len(items)<127,len(items)
(ROOT/'rom/checkpoint_csr.hex').write_text(''.join(f'{v:08x}\n' for a,v in items)+('00000000\n'*(128-len(items))))
(ROOT/'rtl/pace_checkpoint_csr.vh').write_text('''// Generated from the disclosed200M diagnostic checkpoint.
function automatic [6:0] csr_index(input [31:0] address);
 begin case(address)
'''+''.join(f"  32'h{a:08x}:csr_index=7'd{i};\n" for i,(a,v) in enumerate(items))+"  default:csr_index=7'd127;\n endcase end\nendfunction\n")
meta=dict(source='application_guide_ramgates_03',steps=p.steps,pc=f'{p.pc:08X}',
    host_firmware_patches=p.diagnostic_firmware_patches,timer_remaining=p.timer_remaining,
    lsi_group=p.lsi_grouped.group,lsi_apr=p.lsi_grouped.apr,eeprom_pointer=p.eeprom.pointer,
    registers={f'{a:08X}':dict(index=i,value=f'{v:08X}') for i,(a,v) in enumerate(items)})
meta['files']={q.name:hashlib.sha256(q.read_bytes()).hexdigest() for q in [out/'RAM.bin',out/'STATE.bin']}
(out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
print('Exported CPU69words,16MiB RAM,',len(items),'CSR seeds, EEPROM and LSI settings')
