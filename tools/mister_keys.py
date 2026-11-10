#!/usr/bin/env python3
"""Inject key presses on the MiSTer through /dev/uinput (runs on the MiSTer).

Usage: mister_keys.py KEY[:delay_s] ...   e.g.  mister_keys.py f1:3 enter:8 esc:2 enter
Names: f1..f10 enter esc up down left right pgup pgdn 0-9 s i r g y b space
Each key is pressed, held 80 ms, released; the optional delay (default 1 s)
is waited afterwards. Pure standard library (no evdev module on MiSTer).
"""
import fcntl, os, struct, sys, time

KEYS = {'esc': 1, '1': 2, '2': 3, '3': 4, '4': 5, '5': 6, '6': 7, '7': 8, '8': 9, '9': 10, '0': 11,
        'enter': 28, 's': 31, 'i': 23, 'r': 19, 'g': 34, 'y': 21, 'b': 48, 'space': 57,
        'f1': 59, 'f2': 60, 'f3': 61, 'f4': 62, 'f5': 63, 'f6': 64, 'f7': 65, 'f8': 66, 'f9': 67, 'f10': 68,
        'up': 103, 'left': 105, 'right': 106, 'down': 108, 'pgup': 104, 'pgdn': 109, 'h': 35, 't': 20}
UI_SET_EVBIT, UI_SET_KEYBIT, UI_DEV_CREATE, UI_DEV_DESTROY = 0x40045564, 0x40045565, 0x5501, 0x5502
EV_SYN, EV_KEY = 0, 1


def event(fd, etype, code, value):
    now = time.time()
    os.write(fd, struct.pack('llHHi', int(now), int((now % 1) * 1e6), etype, code, value))


def main():
    steps = []
    for arg in sys.argv[1:]:
        name, _, delay = arg.partition(':')
        steps.append((KEYS[name.lower()], float(delay) if delay else 1.0))
    fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    for code in set(KEYS.values()):
        fcntl.ioctl(fd, UI_SET_KEYBIT, code)
    os.write(fd, struct.pack('80sHHHHi', b'Pace remote keys', 3, 0x1234, 0x5678, 1, 0) + bytes(4 * 64 * 4))
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(2.5)  # let MiSTer Main open the new input device
    for code, delay in steps:
        event(fd, EV_KEY, code, 1); event(fd, EV_SYN, 0, 0)
        time.sleep(0.08)
        event(fd, EV_KEY, code, 0); event(fd, EV_SYN, 0, 0)
        time.sleep(delay)
    time.sleep(0.3)
    fcntl.ioctl(fd, UI_DEV_DESTROY)
    os.close(fd)


if __name__ == '__main__':
    main()
