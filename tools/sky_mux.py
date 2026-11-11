#!/usr/bin/env python3
"""Weave a Sky SI/OpenTV table carousel into a constant-rate A/V transport stream.

  sky_mux.py AV.ts SI.ts OUT.ts --video 0x200 --audio 0x102 [--keep PID ...]
             [--rate 6250000] [--si-rate 1000000] [--period SECONDS] [--anchor HH:MM:SS]

AV.ts is a CBR mux (ffmpeg -muxrate RATE). Every packet that is not one of the
A/V PIDs (ffmpeg's own PAT/PMT/SDT and null stuffing) becomes a free slot.
SI.ts (the looped table carousel made by sky_streamer.py, paced at --si-rate)
keeps its own timing: each non-null SI packet goes into the first free slot at
or after its due time, repeating the carousel for the length of the output.
Continuity counters of the SI PIDs are rewritten so repeats are seamless.

The output is a stream file for the core's streamer (rtl/pace_ts_stream.sv):
 - packet 0 is a Pace stream-info packet (PID 0x1FFE, "PACESTRM" + the UTC
   second of the day at which byte 0 is on air), when --anchor is given;
 - with --period, the file is padded with stuffing (or cut) to exactly the
   period at RATE, so the stream loops in step with the EPG schedule;
 - the packet count is even, so the file is a whole number of 8-byte words.
Input and output are streamed; files of any length are handled.
"""
import argparse, sys

P = 188
NULL = bytes([0x47, 0x1f, 0xff, 0x10]) + bytes([0xff]) * 184


def pid(p):
    return ((p[1] & 0x1f) << 8) | p[2]


def info_packet(anchor):
    payload = b'PACESTRM' + anchor.to_bytes(4, 'big')
    return bytes([0x47, 0x1f, 0xfe, 0x10]) + payload + bytes([0xff]) * (184 - len(payload))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('av'); ap.add_argument('si'); ap.add_argument('out')
    ap.add_argument('--video', type=lambda n: int(n, 0), default=0x200)
    ap.add_argument('--audio', type=lambda n: int(n, 0), default=0x102)
    ap.add_argument('--keep', type=lambda n: int(n, 0), action='append', default=[],
                    help='Further A/V PIDs to pass through (repeatable)')
    ap.add_argument('--rate', type=int, default=6250000)
    ap.add_argument('--si-rate', type=int, default=1000000)
    ap.add_argument('--period', type=float, help='Loop period in seconds (pads/cuts the file to match)')
    ap.add_argument('--anchor', help='HH:MM[:SS] UTC at which byte 0 is on air (adds the stream-info packet)')
    ap.add_argument('--max-bytes', type=int, default=0, help='Cut the A/V input to this many bytes')
    a = ap.parse_args()
    av_pids = {a.video, a.audio, *a.keep}
    si = open(a.si, 'rb').read()
    if len(si) % P:
        sys.exit('SI input must be whole 188-byte packets')
    carousel = [(i * P * 8 / a.si_rate, si[i * P:(i + 1) * P]) for i in range(len(si) // P)
                if pid(si[i * P:(i + 1) * P]) != 0x1fff]
    period = len(si) * 8 / a.si_rate
    target = None
    if a.period:
        target = int(round(a.period * a.rate / 8 / (2 * P))) * 2 * P
    out = open(a.out, 'wb')
    written = 0
    cc = {}
    k = placed = late = 0
    worst = 0.0

    def emit(pkt):
        nonlocal written
        out.write(pkt)
        written += P

    if a.anchor:
        hh, mm, *ss = (int(x) for x in a.anchor.split(':'))
        emit(info_packet(hh * 3600 + mm * 60 + (ss[0] if ss else 0)))
    slot = written // P
    with (sys.stdin.buffer if a.av == '-' else open(a.av, 'rb')) as fh:
        while True:
            if target is not None and written >= target:
                break
            if a.max_bytes and (slot * P) >= a.max_bytes:
                break
            pkt = fh.read(P)
            if len(pkt) < P:
                break
            if pkt[0] != 0x47:
                sys.exit(f'A/V sync lost at output packet {slot}')
            if pid(pkt) in av_pids:
                emit(pkt)
            else:
                now = slot * P * 8 / a.rate
                due, sp = carousel[k % len(carousel)]
                due += (k // len(carousel)) * period
                if due <= now:
                    p_ = pid(sp)
                    c = cc.get(p_, 0)
                    cc[p_] = (c + 1) & 15
                    emit(sp[:3] + bytes([(sp[3] & 0xf0) | c]) + sp[4:])
                    k += 1
                    placed += 1
                    if now - due > 0.05:
                        late += 1
                    worst = max(worst, now - due)
                else:
                    emit(NULL)
            slot += 1
    pad = 0
    while (target is not None and written < target) or (written // P) % 2:
        emit(NULL)
        pad += 1
    out.close()
    print(f'{written} bytes, {written*8/a.rate:.3f} s at {a.rate} bit/s; SI packets {placed} '
          f'({k/len(carousel):.2f} carousel loops), >50 ms late {late}, worst {worst*1000:.0f} ms, '
          f'stuffing appended {pad} packets' + (f', anchor {a.anchor}' if a.anchor else ''))


if __name__ == '__main__':
    main()
