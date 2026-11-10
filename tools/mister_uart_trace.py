#!/usr/bin/env python3
"""Runs on MiSTer: capture the core's debug UART (/dev/ttyS1, 115200) for N
seconds and print the MMIO trace lines ("Tw aaaaaaaa dddddddd"); telemetry
frames are dropped unless --all."""
import os, sys, time, termios
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 30
fd = os.open('/dev/ttyS1', os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
a = termios.tcgetattr(fd)
a[0] = 0; a[1] = 0; a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL; a[3] = 0
a[4] = a[5] = termios.B115200
termios.tcsetattr(fd, termios.TCSANOW, a)
buf = b''; t0 = time.time()
while time.time() - t0 < secs:
    try:
        chunk = os.read(fd, 4096)
    except BlockingIOError:
        chunk = b''
    if not chunk:
        time.sleep(0.01); continue
    buf += chunk
    while b'\n' in buf:
        line, buf = buf.split(b'\n', 1)
        line = line.strip().decode('ascii', 'replace')
        if line.startswith('T') and len(line) == 20:
            print(f'{time.time()-t0:7.2f} {"W" if line[1]=="1" else "R"} {line[3:11]} {line[12:20]}', flush=True)
        elif '--all' in sys.argv:
            print(line, flush=True)
