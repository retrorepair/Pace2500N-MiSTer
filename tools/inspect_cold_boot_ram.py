"""Read-only cold-boot evidence: DMA7 descriptor, image resources, retained asserts.

These are addresses in this U202 application, established through Ghidra.
An external RAM dump does not include newer dirty CPU cache lines.
"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ram', type=Path)
    args = parser.parse_args()
    ram = args.ram.read_bytes()
    if len(ram) != 16 * 1024 * 1024:
        parser.error(f'Expected a complete 16 MiB dump, got {len(ram)} bytes')

    def word(address):
        offset = address & 0x1fffffff
        return int.from_bytes(ram[offset:offset + 4], 'big')

    print('External RAM only; dirty CPU cache lines may contain newer values.')
    descriptor = [word(0x108b78 + 4 * index) for index in range(10)]
    print('DMA7 descriptor 00108B78:', ' '.join(f'{value:08X}' for value in descriptor))
    print(f'  destination={descriptor[4]:08X} end={descriptor[8]:08X} '
          f'row_width={descriptor[5] & 0x3fff} gap={descriptor[7]}')
    for index in range(6):
        at = 0x161fcc + 12 * index
        print(f'Image slot {index + 1} at {at:08X}: '
              + ' '.join(f'{word(at + offset):08X}' for offset in (0, 4, 8)))

    # The o-code assert helper passes {format, source-id string, line}. These
    # can remain in an old VM stack, so label them as retained, not live faults.
    needle = b'Assert : F:%s, L:%d.'
    at = -1
    seen = set()
    while True:
        at = ram.find(needle, at + 1)
        if at < 0:
            break
        for segment in (0x80000000, 0xa0000000):
            pointer = (segment | at).to_bytes(4, 'big')
            ref = -1
            while True:
                ref = ram.find(pointer, ref + 1)
                if ref < 0:
                    break
                source = word(ref + 4) & 0x1fffffff
                line = word(ref + 8)
                name = ram[source:source + 16].split(b'\0', 1)[0]
                if name.isdigit() and 0 < line < 10000 and (name, line) not in seen:
                    seen.add((name, line))
                    print(f'Retained assert args at {ref:08X}: source={name.decode()} line={line}')


if __name__ == '__main__':
    main()
