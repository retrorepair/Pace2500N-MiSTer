#!/usr/bin/env python3
"""Runs on the MiSTer: press keys one after another through a virtual keyboard (uinput), e.g.
`mister_keys.py 88 108 108 28 88` = F12, Down, Down, Enter, F12. A code written a+b is a
combination (keys a and b held together), e.g. 125+99. Linux key codes: F12 88, Up 103,
Down 108, Left 105, Right 106, Enter 28, Esc 1."""
import fcntl, os, struct, sys, time
steps = [[int(c) for c in a.split('+')] for a in sys.argv[1:]]
def ev(fd, t, c, v):
    n = time.time(); os.write(fd, struct.pack('llHHi', int(n), int((n % 1) * 1e6), t, c, v))
fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
fcntl.ioctl(fd, 0x40045564, 1)                          # UI_SET_EVBIT EV_KEY
for c in sorted({c for s in steps for c in s}): fcntl.ioctl(fd, 0x40045565, c)   # UI_SET_KEYBIT
os.write(fd, struct.pack('80sHHHHi', b'Pace keys', 3, 0x1234, 0x5679, 1, 0) + bytes(4 * 64 * 4))
fcntl.ioctl(fd, 0x5501); time.sleep(2.5)                 # UI_DEV_CREATE; let the menu program see it
for s in steps:
    for c in s: ev(fd, 1, c, 1); ev(fd, 0, 0, 0); time.sleep(0.05)
    time.sleep(0.15)
    for c in reversed(s): ev(fd, 1, c, 0); ev(fd, 0, 0, 0); time.sleep(0.05)
    time.sleep(0.35)
time.sleep(0.5); fcntl.ioctl(fd, 0x5502); os.close(fd)  # UI_DEV_DESTROY
