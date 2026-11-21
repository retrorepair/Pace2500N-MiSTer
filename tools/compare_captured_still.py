"""Inspect a native PAL DMA7 image in a full external-RAM dump.

The image has two packed 720x288 Y fields followed by two packed 720x144
interleaved U/V fields. Export unsigned planar YUV420 for independent viewing
or compare against a decoder's raw YUV420 output. RAM dumps may lag CPU caches.
"""
import argparse
from pathlib import Path


WIDTH, HEIGHT = 720, 576
Y_BYTES = WIDTH * HEIGHT
IMAGE_BYTES = Y_BYTES * 3 // 2


def extract(ram, base, legacy=False):
    if len(ram) != 16 * 1024 * 1024:
        raise ValueError('expected a complete 16 MiB external-RAM dump')
    if base < 0 or base & 7 or base + IMAGE_BYTES > len(ram):
        raise ValueError('image base must be aligned to eight bytes and fit in RAM')
    y_bases = base, base + Y_BYTES // 2
    uv_bases = base + Y_BYTES, base + Y_BYTES * 5 // 4
    y = b''.join(ram[y_bases[row % 2] + (row // 2) * WIDTH:
                    y_bases[row % 2] + (row // 2 + 1) * WIDTH]
                 for row in range(HEIGHT))
    u, v = bytearray(), bytearray()
    for row in range(HEIGHT // 2):
        offset = uv_bases[row % 2] + (row // 2) * WIDTH
        chroma = ram[offset:offset + WIDTH]
        u.extend(chroma[0::2])
        v.extend(chroma[1::2])
    if legacy:
        # W/X copied the decoder's signed samples and inverted U/V bank names.
        # This option diagnoses OLD dumps; current DMA7 must already convert.
        return bytes(value ^ 128 for value in y + v + u)
    return y + u + v


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ram', type=Path)
    parser.add_argument('--base', required=True, type=lambda value: int(value, 0))
    parser.add_argument('--reference', type=Path, help='unsigned planar YUV420, 720x576')
    parser.add_argument('--output', type=Path, help='write unsigned planar YUV420')
    parser.add_argument('--legacy-signed-swapped', action='store_true')
    parser.add_argument('--tolerance', type=int, default=1, help='allowed IDCT rounding difference')
    args = parser.parse_args()
    if not 0 <= args.tolerance <= 255:
        parser.error('tolerance must be between 0 and 255')
    try:
        image = extract(args.ram.read_bytes(), args.base, args.legacy_signed_swapped)
        if args.output:
            inputs = [args.ram] + ([args.reference] if args.reference else [])
            if any(args.output.resolve() == path.resolve() for path in inputs):
                raise ValueError('output must not overwrite a source file')
            args.output.write_bytes(image)
        failed = 0
        if args.reference:
            reference = args.reference.read_bytes()
            if len(reference) != IMAGE_BYTES:
                raise ValueError('reference must be exactly 622080 bytes (one PAL YUV420 frame)')
            for name, start, end in (('Y', 0, Y_BYTES),
                                     ('U', Y_BYTES, Y_BYTES * 5 // 4),
                                     ('V', Y_BYTES * 5 // 4, IMAGE_BYTES)):
                errors = [abs(a - b) for a, b in zip(image[start:end], reference[start:end])]
                over = sum(error > args.tolerance for error in errors)
                failed += over
                print(f'{name}: max difference {max(errors)}, mean {sum(errors) / len(errors):.4f}, '
                      f'{over} samples exceed {args.tolerance}')
            if failed:
                parser.exit(1, f'{failed} captured samples differ beyond tolerance\n')
            print('PASS: all 622080 captured samples match the independent reference')
        else:
            print(f'Extracted {len(image)} unsigned YUV420 bytes')
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
