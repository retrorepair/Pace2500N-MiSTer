"""Decode the FPGA's frozen PROF instruction/bus ring from a UART capture.

Read-only. Uses the last frozen write pointer and the latest copy of each page,
so an incomplete early UART pass cannot replace later settled trace data.
Output contains firmware-derived addresses and values; keep it in re/deployment.
"""
import argparse
import re
from pathlib import Path


def decode(text):
    epochs = {}
    latest = None
    for match in re.finditer(r'\bPROF\s+((?:[0-9A-Fa-f]{8}\s+){15}[0-9A-Fa-f]{8})', text):
        words = [int(word, 16) for word in match[1].split()]
        header = words[0]
        if header & 0xff800000 != 0xa5800000:
            continue
        latest = header & 0xffffff00
        epochs.setdefault(latest, {})[header & 255] = words[1:]
    if latest is None:
        raise ValueError('No frozen trace in this capture')
    pages = epochs[latest]
    instructions, bus = {}, {}
    for page, words in pages.items():
        if page < 205:
            for slot in range(5):
                index = page * 5 + slot
                if index < 1024:
                    instructions[index] = words[slot * 3:slot * 3 + 3]
        elif page < 227:
            for slot in range(3):
                index = (page - 205) * 3 + slot
                if index < 64:
                    bus[index] = words[slot * 5:slot * 5 + 5]
    return latest, pages, instructions, bus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    try:
        header, pages, instructions, bus = decode(args.capture.read_text(errors='replace'))
    except ValueError as error:
        parser.exit(1, f'{error}\n')
    print(f'Frozen pointer {(header >> 8) & 1023}; pages {len(pages)}/227; '
          f'instructions {len(instructions)}/1024; bus {len(bus)}/64')
    if len(instructions) != 1024 or len(bus) != 64:
        if not args.allow_partial:
            parser.exit(1, 'Incomplete trace; capture more pages or use --allow-partial\n')
    print('\nInstructions, oldest to newest')
    for index in sorted(instructions, reverse=True):
        pc, register, value = instructions[index]
        target = f'r{register & 31:02d}' if register & 32 else '---'
        print(f'{pc:08X} {target} {value:08X}')
    print('\nBus transactions, oldest to newest; data words are raw bus byte order')
    for index in sorted(bus, reverse=True):
        address, flags, *data = bus[index]
        operation = 'R' if flags & 8 else 'W'
        alias = f' KSEG1={address | 0xa0000000:08X}' if flags & 1 else ''
        print(f'{operation} {address:08X} flags={flags:03X} '
              + ' '.join(f'{word:08X}' for word in data) + alias)


if __name__ == '__main__':
    main()
