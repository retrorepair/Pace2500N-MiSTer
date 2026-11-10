"""Export actual guest-programmed filters for native FPGA section delivery."""
import gzip
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
with gzip.open(ROOT / 're/application_guide_ramgates_03.pkl.gz', 'rb') as source:
    p = pickle.load(source)
pid = [p.demux_regs.get(0x14 + 4 * ch, 0) for ch in range(32)]
pointers = [p.demux_banks[0x124].get(ch * 4, ch * 0x3000) for ch in range(32)]
limits = [p.demux_banks[0x124].get(ch * 4 + 2, (ch + 1) * 0x3000 - 32) for ch in range(32)]
matches = [p.demux_banks[0x144].get((index << 4) | unit, 0)
           for unit in range(16) for index in range(16)]
for name, words in [('pid', pid), ('pointer', pointers), ('limit', limits), ('match', matches)]:
    (ROOT / f'rom/checkpoint_demux_{name}.hex').write_text(''.join(f'{w:08x}\n' for w in words))
(ROOT / 'rtl/pace_checkpoint_demux_match.vh').write_text(
    '// Generated from actual guest filter writes in the 200M checkpoint.\n'
    'function automatic [31:0] match_seed_word(input [7:0] index);\n'
    ' begin case(index)\n' + ''.join(f"  8'h{i:02x}:match_seed_word=32'h{v:08x};\n"
                                    for i, v in enumerate(matches) if v) +
    "  default:match_seed_word=32'd0;\n endcase end\nendfunction\n")
meta = dict(source='application_guide_ramgates_03', steps=p.steps,
            control=f'{p.demux_regs[0x140]:08x}', enable=f'{p.demux_regs[0xd8]:08x}',
            armed=[dict(channel=ch, pid=f'{word & 0x1fff:04x}')
                   for ch, word in enumerate(pid) if word >> 13 and word & 0x1fff != 0x1fff])
(ROOT / 're/fpga_guide_checkpoint/demux_manifest.json').write_text(json.dumps(meta, indent=2) + '\n')
print(json.dumps(meta))
