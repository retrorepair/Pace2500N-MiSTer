"""Prepare the DMA7 decoder regression directly from the operator's U202 flash.

No RAM/state image or bundled picture is required. The six drain blocks mirror
the firmware's 524-byte end-code blocks (8000FA04; literal at 9FC223FC).
"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('flash', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.resolve() == args.flash.resolve():
        parser.error('Output must not overwrite the original firmware')
    flash = args.flash.read_bytes()
    if len(flash) != 2 * 1024 * 1024 or flash[0x223fc:0x22400] != b'\0\0\1\xb7':
        parser.error('Expected this application\'s original 2 MiB U202 firmware')
    start = flash.find(b'\0\0\1\xb3\x2d\x02\x40')  # 720x576 sequence header
    end = flash.find(b'\0\0\1\xb7', start + 7) if start >= 0 else -1
    if start < 0 or end < 0 or not 64 < end + 4 - start < 65536:
        parser.error('PAL Guide still image not found in the firmware')
    image = flash[start:end + 4]
    block = bytes(520) + flash[0x223fc:0x22400]
    data = image + block * 6
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(f'{value:02x}\n' for value in data), encoding='ascii')
    print(f'Flash offset {start:06X}: original {len(image)} bytes; '
          f'with driver drain blocks {len(data)} bytes')


if __name__ == '__main__':
    main()
