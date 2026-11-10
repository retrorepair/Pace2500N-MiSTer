#!/usr/bin/env python3
"""Resolve OpenTV o-code native calls (module, function) to firmware functions.

The native table pointer is at 0x8006E71C; the table itself (built at boot,
0x80120050) holds {function array, count} pairs per module. Each array word
points at an 8-byte {shim, argument descriptor} pair in flash; the 16-byte MIPS16
shim loads the real implementation from a PC-relative pool word.

Usage: opentv_natives.py RAM.bin FLASH_U202.bin [module:function ...]
With no calls given, prints every resolved native.
"""
import struct, sys

ram = open(sys.argv[1], 'rb').read()
flash = open(sys.argv[2], 'rb').read()


def word(a):
    a &= 0xffffffff
    if 0x80000000 <= a < 0x81000000:
        o = a & 0xffffff
        return struct.unpack('>I', ram[o:o + 4])[0]
    if 0x9fc00000 <= a < 0x9fe00000 or 0xbfc00000 <= a < 0xbfe00000:
        o = a & 0x1fffff
        return struct.unpack('>I', flash[o:o + 4])[0]
    return None


def half(a):
    w = word(a & ~3)
    return (w >> 16) & 0xffff if (a & 2) == 0 else w & 0xffff


def resolve(module, function):
    table = word(0x8006e71c)
    array, count = word(table + module * 8), word(table + module * 8 + 4)
    if not count or function >= count:
        return None
    pair = word(array + function * 4)
    shim = word(pair)
    real = None
    if shim is not None and shim & 1:          # MIPS16 shim: find lw rx, imm(pc)
        pc = shim & ~1
        for k in range(0, 16, 2):
            h = half(pc + k)
            if h >> 11 == 0x16:
                real = word(((pc + k) & ~3) + (h & 0xff) * 4)
                break
    return pair, shim, real


if __name__ == '__main__':
    calls = [tuple(int(x, 0) for x in a.split(':')) for a in sys.argv[3:]]
    if not calls:
        table = word(0x8006e71c)
        calls = [(m, f) for m in range(64) for f in range(word(table + m * 8 + 4) or 0)]
    for m, f in calls:
        r = resolve(m, f)
        if r:
            pair, shim, real = r
            print(f'({m},0x{f:02x}) pair {pair:08x} shim {shim:08x} impl {real:08x}' if real is not None
                  else f'({m},0x{f:02x}) pair {pair:08x} shim {shim:08x} impl ?')
