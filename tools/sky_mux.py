#!/usr/bin/env python3
"""Weave a Sky SI/OpenTV replay TS into a constant-rate A/V transport stream.

  sky_mux.py AV.ts SI.ts OUT.ts --video 0x200 --audio 0x102 [--rate 6250000] [--si-rate 1000000]

AV.ts is a CBR mux (ffmpeg -muxrate RATE). Every packet that is not the video
or audio PID (ffmpeg's own PAT/PMT/SDT and null stuffing) becomes a free slot.
SI.ts (the looped table carousel made by sky_streamer.py, paced at --si-rate)
keeps its own timing: each non-null SI packet goes into the first free slot at
or after its due time, repeating the carousel for the length of the A/V
stream. Continuity counters of the SI PIDs are rewritten so repeats are
seamless. PCRs stay where ffmpeg put them (same packet positions, same rate).
"""
import argparse, sys

P = 188


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('av'); ap.add_argument('si'); ap.add_argument('out')
    ap.add_argument('--video', type=lambda n: int(n, 0), default=0x200)
    ap.add_argument('--audio', type=lambda n: int(n, 0), default=0x102)
    ap.add_argument('--rate', type=int, default=6250000)
    ap.add_argument('--si-rate', type=int, default=1000000)
    ap.add_argument('--max-bytes', type=int, default=0, help='Truncate output to this many bytes (whole packets)')
    a = ap.parse_args()
    av = open(a.av, 'rb').read(); si = open(a.si, 'rb').read()
    if len(av) % P or len(si) % P:
        sys.exit('inputs must be whole 188-byte packets')
    if a.max_bytes:
        av = av[:a.max_bytes // P * P]
    pid = lambda p: ((p[1] & 0x1f) << 8) | p[2]
    carousel = [(i * P * 8 / a.si_rate, si[i * P:(i + 1) * P]) for i in range(len(si) // P)
                if pid(si[i * P:(i + 1) * P]) != 0x1fff]
    period = len(si) * 8 / a.si_rate
    out = bytearray(); cc = {}; k = 0; placed = late = 0; worst = 0.0
    null = bytes([0x47, 0x1f, 0xff, 0x10]) + bytes([0xff]) * 184
    for i in range(len(av) // P):
        pkt = av[i * P:(i + 1) * P]
        if pkt[0] != 0x47:
            sys.exit(f'A/V sync lost at packet {i}')
        if pid(pkt) in (a.video, a.audio):
            out += pkt; continue
        now = i * P * 8 / a.rate
        due, sp = carousel[k % len(carousel)]
        due += (k // len(carousel)) * period
        if due <= now:
            p = pid(sp); c = cc.get(p, 0); cc[p] = (c + 1) & 15
            out += sp[:3] + bytes([(sp[3] & 0xf0) | c]) + sp[4:]
            k += 1; placed += 1
            if now - due > 0.05: late += 1
            worst = max(worst, now - due)
        else:
            out += null
    open(a.out, 'wb').write(out)
    print(f'{len(out)} bytes, {len(out)*8/a.rate:.2f} s at {a.rate} bit/s; SI packets placed {placed} '
          f'({k/len(carousel):.2f} carousel loops), >50 ms late {late}, worst {worst*1000:.0f} ms')


if __name__ == '__main__':
    main()
