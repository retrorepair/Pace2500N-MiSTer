"""Reconstruct guest filter subscriptions from native RTL MMIO evidence."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('trace', type=Path)
args = parser.parse_args()
pid = [int(s, 16) for s in (ROOT / 'rom/checkpoint_demux_pid.hex').read_text().split()]
words = [int(s, 16) for s in (ROOT / 'rom/checkpoint_demux_match.hex').read_text().split()]
enable = 0xffc00000
latch = 0
step = 0
for line in args.trace.read_text().splitlines():
    match = re.search(r'RET\s+(\d+) PC \w+ IO 1 b000a([0-9a-f]{3}) ([0-9a-f]{8})', line)
    if not match:
        continue
    step, off, value = int(match[1]), int(match[2], 16), int(match[3], 16)
    if 0x14 <= off < 0x94:
        pid[(off - 0x14) // 4] = value
    elif off == 0xd8:
        enable |= value
    elif off == 0x148:
        latch = value
    elif off == 0x144 and value & 0xc000 == 0xc000:
        words[(value & 15) * 16 + (value >> 4 & 15)] = latch
result = []
for channel, value in enumerate(pid):
    if not (enable >> channel & 1 and value >> 13 and value & 0x1fff != 0x1fff):
        continue
    units = []
    routes = words[(channel & 15) * 16 + (9 if channel >= 16 else 8)]
    for unit in range(32):
        if not routes >> unit & 1:
            continue
        rules = []
        for index in range(8):
            pair = words[(unit // 2) * 16 + index] >> (16 if unit & 1 else 0) & 0xffff
            if pair & 255:
                rules.append(dict(offset=index + 2 if index else 0,
                                  value=f'{pair >> 8:02X}', mask=f'{pair & 255:02X}'))
        units.append(dict(unit=unit, rules=rules))
    result.append(dict(channel=channel, pid=f'{value & 0x1fff:04X}', units=units))
print(json.dumps(dict(last_write_step=step, armed=result), indent=2))
