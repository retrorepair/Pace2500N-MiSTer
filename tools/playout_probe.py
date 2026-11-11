#!/usr/bin/env python3
"""Act as the MiSTer relay for N seconds and report what the playout server sends.

  playout_probe.py [--server 127.0.0.1:8250] [--video 0x4210] [--audio 0x4112] [--seconds 10]

Checks: 188-byte sync throughout, the byte rate against 781,250 B/s, packets
per PID (the tuned A/V PIDs, the SI PIDs), continuity counters, and that the
guide tables (PAT, SDT, BAT, TOT, titles) are present.
"""
import argparse, socket, time

ap = argparse.ArgumentParser()
ap.add_argument('--server', default='127.0.0.1:8250')
ap.add_argument('--video', default='0x4210')
ap.add_argument('--audio', default='0x4112')
ap.add_argument('--seconds', type=float, default=10)
ap.add_argument('--save')
a = ap.parse_args()
host, port = a.server.rsplit(':', 1)
s = socket.create_connection((host, int(port)), timeout=30)
s.sendall(f'GET /tune?video={a.video}&audio={a.audio} HTTP/1.0\r\nHost: x\r\n\r\n'.encode())
data = b''
t0 = time.time()
first = None
while time.time() - t0 < a.seconds:
    part = s.recv(65536)
    if not part:
        break
    if first is None:
        first = time.time() - t0
    data += part
s.close()
head, body = data.split(b'\r\n\r\n', 1)
print(head.split(b'\r\n')[0].decode(), f'first data after {first:.2f} s, {len(body)} bytes in {a.seconds:.0f} s')
n = len(body) // 188
bad = sum(1 for i in range(n) if body[i * 188] != 0x47)
pids, cc_err, last = {}, 0, {}
tables = set()
for i in range(n):
    p = body[i * 188:(i + 1) * 188]
    pid = ((p[1] & 0x1f) << 8) | p[2]
    pids[pid] = pids.get(pid, 0) + 1
    if pid != 0x1fff:
        c = p[3] & 15
        if pid in last and c != (last[pid] + 1) & 15:
            cc_err += 1
        last[pid] = c
    if p[1] & 0x40 and pid < 0x100:
        tables.add((pid, p[5]))
print(f'packets {n}, sync errors {bad}, continuity errors {cc_err}')
for pid, cnt in sorted(pids.items(), key=lambda x: -x[1])[:14]:
    print(f'  PID {pid:04x}: {cnt} packets ({cnt * 188 * 8 / max(1, a.seconds) / 1000:.0f} kbit/s)')
print('section starts (PID, table):', ' '.join(f'{p:02x}/{t:02x}' for p, t in sorted(tables)))
if a.save:
    open(a.save, 'wb').write(body[:n * 188])
