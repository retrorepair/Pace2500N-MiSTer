"""Protocol edge cases and independently generated native RTL replay vectors."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from pace_transport import Packetizer, SectionAssembler, crc32_mpeg, validate_section
from pace_si import long_section, tot


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.section = long_section(0x42, 0x1234, bytes(range(256)) * 3)

    def test_known_crc(self):
        self.assertEqual(crc32_mpeg(b'123456789'), 0x0376e6e7)

    def test_all_chunk_sizes(self):
        stream = Packetizer().section(17, self.section)
        for size in (1, 2, 7, 187, 188, 189, 377, 1024):
            assembler = SectionAssembler()
            got = []
            for offset in range(0, len(stream), size):
                got += assembler.feed(stream[offset:offset + size])
            self.assertEqual(got, [(17, self.section)])
            self.assertFalse(assembler.errors)

    def test_duplicate_and_packet_loss_recovery(self):
        packetizer = Packetizer()
        stream = packetizer.section(17, self.section)
        assembler = SectionAssembler()
        self.assertEqual(assembler.feed(stream[:188] + stream[:188] + stream[188:]), [(17, self.section)])
        self.assertEqual(assembler.duplicates, 1)
        assembler = SectionAssembler()
        self.assertEqual(assembler.feed(stream[:188] + stream[376:]), [])
        self.assertEqual(assembler.feed(packetizer.section(17, self.section)), [(17, self.section)])
        self.assertGreater(assembler.errors, 0)

    def test_adaptation_only_continuity(self):
        stream = Packetizer().section(17, self.section)
        adaptation = bytes.fromhex('47001120b700') + b'\xff' * 182
        assembler = SectionAssembler()
        self.assertEqual(assembler.feed(stream[:188] + adaptation + stream[188:]), [(17, self.section)])
        self.assertFalse(assembler.errors)

    def test_pusi_pointer_finishes_previous_then_starts_new(self):
        a = long_section(0x42, 1, b'a' * 200)
        b = long_section(0x42, 2, b'b')
        first = Packetizer().section(17, a)[:188]
        tail = a[183:]
        payload = bytes((len(tail),)) + tail + b
        second = bytes.fromhex('47401111') + payload + b'\xff' * (184 - len(payload))
        self.assertEqual(SectionAssembler().feed(first + second), [(17, a), (17, b)])

    def test_discontinuity_and_bad_adaptation(self):
        stream = Packetizer().section(17, self.section)
        # Explicit discontinuity with no PUSI drops the partial section.
        adaptation = bytes.fromhex('47001120b780') + b'\xff' * 182
        assembler = SectionAssembler()
        self.assertEqual(assembler.feed(stream[:188] + adaptation + stream[188:]), [])
        bad = bytes.fromhex('47401130ff') + b'\xff' * 183
        self.assertEqual(assembler.feed(bad), [])
        self.assertGreater(assembler.errors, 0)

    def test_crc_tot_and_tdt(self):
        when = datetime(2002, 9, 1, 12, tzinfo=timezone.utc)
        validate_section(tot(when))
        validate_section(bytes.fromhex('707005ca00000000'))
        bad = bytearray(tot(when)); bad[-1] ^= 1
        with self.assertRaises(ValueError):
            validate_section(bad)
        with self.assertRaises(ValueError):
            tot(when.replace(tzinfo=None))


def vectors():
    """Expected DMA bytes come directly from input sections, not the RTL model."""
    packetizer = Packetizer()
    when = datetime(2002, 9, 1, 12, tzinfo=timezone.utc)
    a = tot(when)
    b = long_section(0x42, 0x1234, bytes(range(256)) * 3)
    c = long_section(0x40, 0x20, b'network' * 11)
    streams = []
    expected = []
    pointer = {ch: ch * 0x3000 for ch in (22, 23, 24)}

    def add(pid, section, channel):
        wire = packetizer.section(pid, section)
        streams.append(wire)
        # Give the bench time to acknowledge each completion before repetition.
        streams.append(packetizer.null())
        for byte in section + b'\x00':
            expected.append((0x7a0000 + pointer[channel], byte))
            pointer[channel] += 1
        return wire

    duplicate = add(20, a, 22)
    streams.append(duplicate)  # exact duplicate must not create another record
    add(17, b, 23)
    add(16, c, 24)
    # Valid CRC is insufficient: initial SDT/TOT match units must reject BAT
    # and TDT on the same PIDs. This catches the formerly wrong routing ABI.
    streams.append(packetizer.section(17, long_section(0x4a, 0x1000, b'rejected')))
    streams.append(packetizer.section(20, bytes.fromhex('707005cd26120000')))
    corrupted = bytearray(packetizer.section(20, a)); corrupted[20] ^= 1
    streams.append(corrupted)
    lost = packetizer.section(17, b)
    streams.append(lost[:188] + lost[376:])
    add(17, b, 23)
    add(20, a, 22)
    wire = b''.join(streams)
    normal_bytes = len(expected)
    # Extra phase: table_id in the last byte, section_length at the ring's
    # first two bytes. Original helper800044BC explicitly reads this case.
    expected += [(0x7a0000 + 22 * 0x3000 + (0x2fff + i) % 0x3000, byte) for i, byte in enumerate(a + b'\x00')]
    wrap_bytes = len(expected)
    expected += [(0x7a0000 + 22 * 0x3000 + len(a) + i, byte) for i, byte in enumerate(a + b'\x00')]
    expected += [(0x7a0000 + 25 * 0x3000 + i, byte) for i, byte in enumerate(a + b'\x00')]
    out = ROOT / 'sim/transport_vectors'; out.mkdir(exist_ok=True)
    padded = wire + bytes((-len(wire)) % 8)
    (out / 'ts64.hex').write_text(''.join(padded[i:i + 8][::-1].hex() + '\n'
                                         for i in range(0, len(padded), 8)))
    (out / 'expected.hex').write_text(''.join(f'{address:06x}{byte:02x}\n' for address, byte in expected))
    (out / 'sizes.vh').write_text(f'localparam TS_BYTES={len(wire)}, DMA_BYTES={len(expected)}, NORMAL_DMA_BYTES={normal_bytes}, WRAP_DMA_BYTES={wrap_bytes};\n')
    print(f'RTL vectors: {len(wire) // 188} packets, {len(expected)} expected DMA bytes, 5 completions')


if __name__ == '__main__':
    if '--vectors' in sys.argv:
        vectors()
    else:
        unittest.main()
