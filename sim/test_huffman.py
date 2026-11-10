import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from pace_huffman import FirmwareHuffman

CASES = ['', ' TEST ONE (Stereo) ', 'NEWS AT 12:00 = TEST',
         'The quick brown fox jumps over the lazy dog. 0123456789']


class NativeTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = FirmwareHuffman.from_file(ROOT / 're/fpga_guide_checkpoint/RAM.bin')

    def test_all_printable_bytes_and_padding(self):
        for n in range(32, 127):
            for count in (1, 2, 3, 4, 5, 6, 7, 8):
                text = bytes((n,)) * count
                self.assertEqual(self.codec.decode(self.codec.encode(text)), text)

    def test_phrase_and_spaces(self):
        self.assertEqual(self.codec.codes[b' '], '110')
        self.assertEqual(self.codec.codes[b'(Stereo)'], '010000111')
        for text in CASES:
            self.assertEqual(self.codec.decode(self.codec.encode(text)), text.encode('ascii'))


def vectors():
    codec = FirmwareHuffman.from_file(ROOT / 're/fpga_guide_checkpoint/RAM.bin')
    out = ROOT / 'sim/huffman_vectors';out.mkdir(exist_ok=True)
    lengths = []
    encoded = bytearray(4 * 256)
    expected = bytearray(4 * 256)
    for i, text in enumerate(CASES):
        data = codec.encode(text);lengths.append(len(data))
        encoded[i * 256:i * 256 + len(data)] = data
        expected[i * 256:i * 256 + len(text)] = text.encode('ascii')
    for name, data in [('input', encoded), ('expected', expected)]:
        (out / f'{name}.hex').write_text(''.join(f'{byte:02x}\n' for byte in data))
    (out / 'lengths.hex').write_text(''.join(f'{n:08x}\n' for n in lengths))
    print('Native decoder cases:', list(zip(CASES, lengths)))


if __name__ == '__main__':
    if '--vectors' in sys.argv:
        vectors()
    else:
        unittest.main()
