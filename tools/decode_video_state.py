"""Decode MV= snapshots from the cold-boot decoder memory diagnostics.

Counters are sampled low bytes, so differences between UART samples cannot
measure throughput or prove that no transactions happened between samples.
"""
import argparse
import re
from collections import Counter
from pathlib import Path


STATES = {
    0: 'INIT', 1: 'REQ', 2: 'RX', 3: 'PROC', 4: 'HIT',
    5: 'FILL_CMD', 6: 'FILL_DAT', 7: 'FILL_DRN', 8: 'SERVE_ADR',
    9: 'SERVE', 10: 'WR_CMD', 11: 'STREAM', 12: 'PEEK',
    13: 'ISSUE2', 14: 'PEEK2',
}
FLAGS = ((31, 'DDR_wait'), (30, 'DDR_read'), (29, 'DDR_write'),
         (28, 'cmd_pop'), (27, 'cmd_valid'), (26, 'response'),
         (25, 'response_full'), (24, 'reset_n'),
         (23, 'enabled'), (22, 'busy'))


def describe(value):
    active = ','.join(name for bit, name in FLAGS if value & (1 << bit)) or '-'
    return (f'{STATES.get((value >> 16) & 15, "UNKNOWN"):<9} '
            f'write_low={(value >> 8) & 255:02X} read_low={value & 255:02X} '
            f'{active}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', nargs='?', type=Path)
    parser.add_argument('--word', type=lambda value: int(value, 16))
    parser.add_argument('--summary', action='store_true', help='show sampled-state counts only')
    args = parser.parse_args()
    if args.word is not None:
        if not 0 <= args.word <= 0xFFFFFFFF:
            parser.error('word must fit 32 bits')
        print(f'{args.word:08X} {describe(args.word)}')
        return
    if args.log is None:
        parser.error('provide a UART log or --word HEX')
    states = Counter()
    previous = None
    for line_number, line in enumerate(args.log.read_text(errors='replace').splitlines(), 1):
        match = re.search(r'\bMV=([0-9a-fA-F]{8})\b', line)
        if not match:
            continue
        value = int(match[1], 16)
        states[value] += 1
        if not args.summary and value != previous:
            print(f'line {line_number:6} MV={value:08X} {describe(value)}')
        previous = value
    print(f'{sum(states.values())} memory snapshots; {len(states)} distinct sampled values')
    if args.summary:
        for value, count in states.most_common():
            print(f'{count:6} samples MV={value:08X} {describe(value)}')


if __name__ == '__main__':
    main()
