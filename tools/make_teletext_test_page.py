#!/usr/bin/env python3
"""Generate a labelled System B page 100 output fixture (not broadcast data)."""
from pathlib import Path

HAMMING = bytes.fromhex('15 02 49 5e 64 73 38 2f d0 c7 8c 9b a1 b6 fd ea')


def parity(value):
    value &= 0x7f
    return value | ((1 ^ (value.bit_count() & 1)) << 7)


def packets():
    lines = {
        2: '\x06PACE 2500N / MISTER',
        4: '\x07PAGE 100 - HSync PDM experiment',
        6: '\x02IF YOU CAN READ THIS:',
        7: '\x07Your TV decoded the VBI test signal.',
        9: '\x03RGB picture is unchanged.',
        11: 'No broadcast or Internet is required.',
        12: 'This page comes from a test fixture.',
        14: '\x01LOW AMPLITUDE - EXPERIMENTAL',
        16: 'F11 on MiSTer: start / stop test.',
        17: 'Returns to normal sync after 30 seconds.',
        19: 'Use your TV remote: Text, then 100.',
        24: '\x06PACE TEST 100',
    }
    for row in range(25):
        address = bytes((HAMMING[1 | ((row & 1) << 3)], HAMMING[row >> 1]))
        if row == 0:
            # Page 100, subpage 0000, erase page, parallel magazine, English.
            payload = bytes(HAMMING[n] for n in (0, 0, 0, 8, 0, 0, 0, 0))
            payload += bytes(map(parity, b'PACE TEST 100   RGB / VBI TEST'.ljust(32)))
        else:
            text = lines.get(row, '').encode('ascii')
            assert len(text) <= 40
            payload = bytes(map(parity, text.ljust(40)))
        # LSB first on the wire; framing 0x27 gives temporal 11100100.
        yield b'\x55\x55\x27' + address + payload


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    page = list(packets())
    assert all(len(p) == 45 for p in page)
    (root / 'rom/teletext_test100.hex').write_text(
        ''.join(f'{value:02x}\n' for packet in page for value in packet), encoding='ascii')
    print('Generated page 100: 25 packets, 1125 bytes')
