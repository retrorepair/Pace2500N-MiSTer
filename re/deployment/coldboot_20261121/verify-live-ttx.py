import re
import sys
from pathlib import Path

r = Path(sys.argv[1])
lines = (r / 'uart.txt').read_text().splitlines()
def mark(name): return int((r / (name + '.idx')).read_text())
def frames(start, end):
    out = []
    for line in lines[start:end]:
        if 'PACE PC=' not in line or ' TT=' not in line: continue
        fields = {k: int(v, 16) for k, v in re.findall(r'\b(\w+)=([0-9A-F]{8})(?= |$)', line)}
        if {'PC', 'IR', 'RET', 'HALT', 'FLASH', 'TT'} <= fields.keys(): out.append(fields)
    return out
start = mark('baseline')
steady = frames(start, len(lines))
raw = [s for s in lines[start:] if 'PACE PC=' in s and ' TT=' in s]
bad = len(raw) - len(steady)
assert len(steady) >= 100 and bad <= 4 and len(steady) >= len(raw) * .95, 'Missing/corrupt UART'
assert not any(re.search(r' HALT=(?!00000000)[0-9A-F]{8}(?= |$)', s) for s in raw), 'CPU halt in malformed frame'
assert all(s['IR'] == 0 and s['HALT'] == 0 and s['FLASH'] == 1 for s in steady), 'CPU/flash regression'
assert len({s['RET'] for s in steady}) > 20, 'CPU stopped retiring'
assert 'qwords differing 0 of 262144' in (r / 'flashcheck.txt').read_text(), 'Flash mismatch'
live = frames(mark('baseline'), mark('live'))
assert len(live) >= 3 and all(s['TT'] & 0xd0000000 == 0xc0000000 for s in live), 'Live VBI missing'
delta = (live[-1]['TT'] - live[0]['TT']) & 65535
assert delta >= 300, 'Transport-fed VBI counter not advancing'
fixture = frames(0, mark('fixture'))[-3:]
assert len(fixture) == 3 and all(s['TT'] & 0x90000000 == 0x90000000 for s in fixture), 'F11 fixed page not running'
for phase in ('expired', 'cancelled'):
    sample = frames(0, mark(phase))[-3:]
    assert len(sample) == 3 and all(s['TT'] & 0xd0000000 == 0xc0000000 for s in sample), phase + ': live service did not resume'
    assert (sample[-1]['TT'] - sample[0]['TT']) & 65535 > 50, phase + ': counter stopped'
assert all(s['TT'] & 0x90000000 == 0x80000000 for s in steady[-5:]), 'Not left in live mode'
print('PASS 240s: exact flash, IR/HALT0, retirement, live VBI packet delta%d, F11 fixture/timeout/cancel, native navigation CPU health' % delta)
print('Malformed UART snapshots reported: %d of%d' % (bad, len(raw)))
print('Actual TV page refresh and timed subtitle overlay still require physical observation.')
