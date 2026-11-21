"""Decode read-only FP= UART snapshots emitted by the cold-boot controller model."""
import argparse
import re
from pathlib import Path


def describe(value):
    flags = [(31, 'clock'), (30, 'tx_queue'), (29, 'tx_valid'), (28, 'reply'),
             (27, 'ack_queue'), (26, 'rx_escape'), (25, 'tx_escape'), (24, 'ready')]
    active = ','.join(name for bit, name in flags if value & (1 << bit)) or '-'
    return (f'{active:<48} RX={(value >> 16) & 255:02X} '
            f'wire={(value >> 12) & 15}/{(value >> 8) & 15} '
            f'tx_count={(value >> 3) & 31} '
            f'GPIO={value >> 2 & 1} CSI={value >> 1 & 1} IRQmask={value & 1}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', nargs='?', type=Path)
    parser.add_argument('--word', type=lambda value: int(value, 16))
    args = parser.parse_args()
    if args.word is not None:
        print(f'{args.word:08X} {describe(args.word)}')
        return
    if args.log is None:
        parser.error('provide a UART log or --word HEX')
    previous = None
    count = 0
    for line_number, line in enumerate(args.log.read_text(errors='replace').splitlines(), 1):
        match = re.search(r'\bFP=([0-9a-fA-F]{8})\b', line)
        if not match:
            continue
        value = int(match[1], 16)
        count += 1
        if value != previous:
            pc = re.search(r'\bPC=([0-9a-fA-F]{8})\b', line)
            print(f'line {line_number:6} PC={pc[1] if pc else "????????"} '
                  f'FP={value:08X} {describe(value)}')
        previous = value
    print(f'{count} controller snapshots; identical consecutive states suppressed')


if __name__ == '__main__':
    main()
