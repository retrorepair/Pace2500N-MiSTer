#!/usr/bin/env python3
"""Runs on the MiSTer: A/B two Live launchers on cold start.

For each run (launchers alternate): load the core, open ALL CHANNELS the way
a viewer does (F1, Enter, every 14 s) and time until its listings are in RAM
(a programme title appears), then select the top row and time until the
firmware routes its PIDs (status block in /tmp/pace_live.ts).
  python3 ab_cores.py A.mgl B.mgl [runs] [title]
Needs /tmp/mister_keys.py.
"""
import mmap, os, struct, subprocess, sys, time

a, b = sys.argv[1], sys.argv[2]
runs = int(sys.argv[3]) if len(sys.argv) > 3 else 3
title = (sys.argv[4] if len(sys.argv) > 4 else 'DuckTales').encode()

fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
ram = mmap.mmap(fd, 0x1000000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x30000000)


def routed():
    st = os.pread(os.open('/tmp/pace_live.ts', os.O_RDONLY), 32, 512)
    return struct.unpack('>HH', st[16:20])


def keys(*k):
    subprocess.run(['python3', '/tmp/mister_keys.py', *k], check=True)


def run(mgl):
    with open('/dev/MiSTer_cmd', 'w') as f:
        f.write('load_core ' + mgl + '\n')
    t0 = time.time()
    time.sleep(45)                      # MGL loads flash, RAM, state; firmware settles
    listed = None; visits = 0
    while time.time() - t0 < 240:       # open ALL CHANNELS until the list is in RAM
        keys('f1:4', 'enter:10'); visits += 1
        if ram[:].count(title) > 0:
            listed = time.time() - t0
            break
    if listed is None:
        return None, None, visits
    t1 = time.time()
    keys('enter:0.2')                   # select the top row of ALL CHANNELS
    tuned = None
    while time.time() - t1 < 60:
        if routed()[0] != 0x1fff:
            tuned = time.time() - t1
            break
        time.sleep(0.25)
    return listed, tuned, visits


res = {a: [], b: []}
for i in range(runs):
    for m in (a, b):
        r = run(m)
        res[m].append(r)
        print(f'run {i+1} {os.path.basename(m)}: listings {r[0] and round(r[0],1)} s, '
              f'select->routed {r[1] and round(r[1],1)} s, ALL CHANNELS visits {r[2]}', flush=True)
for m, rs in res.items():
    ok = [r for r in rs if r[0] is not None and r[1] is not None]
    if ok:
        print(f'{os.path.basename(m)}: {len(ok)}/{len(rs)} ok, listings avg '
              f'{sum(r[0] for r in ok)/len(ok):.1f} s, select->routed avg {sum(r[1] for r in ok)/len(ok):.1f} s')
    else:
        print(f'{os.path.basename(m)}: 0/{len(rs)} ok')
