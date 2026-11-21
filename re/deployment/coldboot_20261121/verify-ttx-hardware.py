import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
lines = (root / 'uart.txt').read_text().splitlines()
def mark(name):
    return int((root / (name + '.idx')).read_text())
def snapshots(start, end):
    frames = []
    for line in lines[start:end]:
        if 'PACE PC=' not in line or ' TT=' not in line:
            continue
        fields = dict((k, int(v, 16)) for k, v in re.findall(r'\b(\w+)=([0-9A-F]{8})(?= |$)', line))
        if {'PC', 'IR', 'RET', 'HALT', 'FLASH', 'TT'} <= fields.keys():
            frames.append(fields)
    return frames
baseline = mark('baseline')
active = snapshots(mark('active-start'), mark('active-end'))
expired = snapshots(0, mark('expired'))[-5:]
cancelled = snapshots(0, mark('cancelled'))[-3:]
steady = snapshots(baseline, len(lines))
raw_steady = [line for line in lines[baseline:] if 'PACE PC=' in line and ' TT=' in line]
malformed = len(raw_steady) - len(steady)
assert malformed <= 2 and len(steady) >= len(raw_steady) * .95, 'Excessive UART corruption'
# Even an otherwise malformed frame must not hide a readable CPU halt.
assert not any(re.search(r' HALT=(?!00000000)[0-9A-F]{8}(?= |$)', line) for line in raw_steady), 'CPU halt in malformed frame'
assert 'qwords differing 0 of 262144' in (root / 'flashcheck.txt').read_text(), 'Flash upload differs'
assert len(active) >= 3 and len(steady) >= 40, 'Missing UART snapshots'
assert all(s['HALT'] == 0 and s['IR'] == 0 and s['FLASH'] == 1 for s in steady), 'CPU/flash regression'
assert len({s['RET'] for s in steady}) > 10, 'CPU stopped retiring instructions'
assert all(s['TT'] & 0xc0000000 == 0xc0000000 for s in active), 'Test not active/PAL locked'
counts = [s['TT'] & 65535 for s in active]
assert counts[-1] - counts[0] >= 100, 'Packets not advancing at field rate'
assert all(s['TT'] & 0x90000000 == 0 and s['TT'] & 0x40000000 for s in expired), '30s timeout failed'
assert all(s['TT'] & 0x90000000 == 0 for s in cancelled), 'Manual cancel failed'
assert all(s['TT'] & 0x90000000 == 0 for s in steady[-5:]), 'Test not left off'
print('PASS flash exact, CPU IR/HALT=0, PAL lock, %d packets across active sample, automatic timeout, manual cancel, final normal CSync' % (counts[-1] - counts[0]))
print('UART malformed snapshots excluded and reported: %d of %d' % (malformed, len(raw_steady)))
print('TV page decoding requires physical observation; an FPGA screenshot cannot capture the TV teletext decoder.')
