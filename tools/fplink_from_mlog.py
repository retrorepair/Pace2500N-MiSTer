"""Decode the front-panel / smartcard micro link (B2009010, full duplex: one byte out per byte in)
from a tb_sys register log (+mlog) into frames: LEN SEQ CODE args..., 0x00 ends a frame, 0x1B
escapes the next byte. Usage: fplink_from_mlog.py MLOG [START_US]"""
import sys
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
def frames(stream):
    out, cur, esc = [], [], False
    for t, b in stream:
        if esc: cur.append(b); esc = False
        elif b == 0x1b: esc = True
        elif b == 0:
            if cur: out.append((t, cur)); cur = []
        else: cur.append(b)
    return out
tx, rx = [], []
for line in open(sys.argv[1]):
    f = line.split()
    if len(f) < 6 or f[3] != 'b2009010' or int(f[0]) < start:
        continue
    (tx if f[2] == 'W' else rx).append((int(f[0]), int(f[5], 16) & 0xff))
ev = [(t, 'box ', fr) for t, fr in frames(tx)] + [(t, 'micro', fr) for t, fr in frames(rx)]
for t, who, fr in sorted(ev):
    print('%10d us  %s  %s' % (t, who, ' '.join('%02x' % b for b in fr)))
