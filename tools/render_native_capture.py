"""Render an actual native-RTL RAM dump using its captured OSD root."""
import argparse
import json
import re
from pathlib import Path
from types import SimpleNamespace
from render_guest_osd import render

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('prefix', type=Path, help='Testbench OUT prefix, e.g. re/transport/native_final')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
state = Path(str(args.prefix) + '_state.txt').read_text()
root = re.search(r'\bOSD ([0-9a-fA-F]+)', state)
steps = re.search(r'RETIRED\s+(\d+)', state)
if not root or not steps:
    raise ValueError('State must capture the actual runtime OSD root and instruction count')
ram = bytearray(16777216)
position = 0
with Path(str(args.prefix) + '_ram64.hex').open() as source:
    for line in source:
        for word in line.split('//')[0].split():
            if word.startswith('@'):
                position = int(word[1:], 16) * 8
            else:
                if position + 8 > len(ram):
                    raise ValueError('RAM dump exceeds 16 MiB')
                ram[position:position + 8] = int(word, 16).to_bytes(8, 'little')
                position += 8
Path(str(args.prefix) + '.bin').write_bytes(ram)
manifest = json.loads((ROOT / 're/fpga_guide_checkpoint/manifest.json').read_text())
probe = SimpleNamespace(ram=ram, steps=int(steps[1]),
                        mmio_streams={(0xb0004200, 4): [int(root[1], 16)]},
                        diagnostic_firmware_patches=manifest['host_firmware_patches'])
metadata = render(probe, str(args.output))
metadata.update(source='native FPGA RTL simulation RAM/OSD root', hardware_capture=False,
                root_source='runtime peripheral output captured in testbench state',
                cpu_execution='pace_firmware_cpu RTL in Verilator',
                decoded_text_locations={text: ram.find(text.encode('ascii'))
                                        for text in ('LOCAL TEST ONE', 'LOCAL TEST TWO', 'TEST ONE 13:00')})
Path(str(args.output) + '.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata, indent=2))
