import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from pace_si import diagnostic_tables, dvb_utc
from pace_huffman import FirmwareHuffman
from pace_transport import validate_section


class NativeSITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = FirmwareHuffman.from_file(ROOT / 're/fpga_guide_checkpoint/RAM.bin')

    def test_known_clock_and_title_record_arithmetic(self):
        when = datetime(2002, 9, 1, 12, tzinfo=timezone.utc)
        self.assertEqual(dvb_utc(when), bytes.fromhex('cd26120000'))
        titles = []
        for pid, section in diagnostic_tables(when, self.codec):
            validate_section(section)
            if not 0xa0 <= section[0] <= 0xa3:
                continue
            self.assertEqual(pid, 0x36)
            self.assertEqual(section[8:10], bytes.fromhex('cd26'))
            position = 10
            while position < len(section) - 4:
                size = int.from_bytes(section[position + 2:position + 4], 'big') & 4095
                desc = section[position + 4:position + 4 + size]
                self.assertEqual(desc[0], 0xb5)
                self.assertEqual(len(desc), desc[1] + 2)
                start = int.from_bytes(desc[2:4], 'big') * 2
                self.assertEqual(start // 21600, section[0] & 3)
                titles.append(self.codec.decode(desc[9:]).decode('ascii'))
                position += size + 4
            self.assertEqual(position, len(section) - 4)
        self.assertEqual(len(titles), 6)
        self.assertIn('LOCAL TEST ONE', titles)
        self.assertIn('NEXT TEST TWO', titles)

    def test_private_row_namespace_and_native_encoding(self):
        when = datetime(2002, 9, 1, 12, tzinfo=timezone.utc)
        sdt = next(s for pid, s in diagnostic_tables(when, self.codec) if s[0] == 0x42)
        position = 11
        decoded = []
        while position < len(sdt) - 4:
            size = int.from_bytes(sdt[position + 3:position + 5], 'big') & 4095
            at = position + 5
            end = at + size
            namespace = False
            while at < end:
                tag, length = sdt[at:at + 2]
                data = sdt[at + 2:at + 2 + length]
                if tag == 0x5f:
                    namespace = data == b'\x00\x00\x00\x02'
                if tag == 0xb2:
                    self.assertTrue(namespace)
                    self.assertEqual(data[:3], bytes((1, 0, 0x60)))
                    decoded.append(self.codec.decode(data[3:]))
                at += length + 2
            self.assertEqual(at, end)
            position = end
        self.assertEqual(decoded, [b'LOCAL TEST ONE', b'LOCAL TEST TWO'])

    def test_full_day_and_index_references(self):
        when = datetime(2002, 9, 1, 12, tzinfo=timezone.utc)
        tables = diagnostic_tables(when, self.codec, full_day=True, with_index=True)
        events = set()
        intervals = {3000: [], 3001: []}
        for pid, section in tables:
            validate_section(section)
            if 0xa0 <= section[0] <= 0xa3:
                listing = int.from_bytes(section[3:5], 'big')
                at = 10
                while at < len(section) - 4:
                    size = int.from_bytes(section[at + 2:at + 4], 'big') & 4095
                    event = int.from_bytes(section[at:at + 2], 'big')
                    start = int.from_bytes(section[at + 6:at + 8], 'big') * 2
                    duration = int.from_bytes(section[at + 8:at + 10], 'big') * 2
                    self.assertEqual(section[0] & 3, start // 21600)
                    events.add((listing, event));intervals[listing].append((start, start + duration))
                    at += size + 4
        self.assertEqual(len(events), 48)
        for spans in intervals.values():
            self.assertEqual(sorted(spans), [(n * 3600, (n + 1) * 3600) for n in range(24)])
        indices = [(pid, s) for pid, s in tables if s[0] == 0xc1]
        self.assertEqual(len(indices), 34)
        for pid, section in indices:
            self.assertEqual(pid, 0x52)
            self.assertEqual((len(section) - 12) % 9, 0)
            for at in range(8, len(section) - 4, 9):
                reference = (int.from_bytes(section[at:at + 2], 'big'),
                             int.from_bytes(section[at + 5:at + 7], 'big'))
                self.assertIn(reference, events)


if __name__ == '__main__':
    unittest.main()
