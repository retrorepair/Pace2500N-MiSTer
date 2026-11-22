"""System B text pages and bounded DVB Teletext transport, no OCR or video burn-in.

Canonical PES fits three 44-byte EN300472 data units in one 188-byte TS packet.
The optional FPGA bridge listens on PID 0x1EF0. All text on the wire has odd
parity; DVB bit order is converted here, not by an undocumented TV convention.
"""
import html
import re
import textwrap
import unicodedata
from collections import deque
from dataclasses import dataclass

PID = 0x1ef0
HAM = bytes.fromhex('15 02 49 5e 64 73 38 2f d0 c7 8c 9b a1 b6 fd ea')
REVERSE = bytes(int(f'{n:08b}'[::-1], 2) for n in range(256))


def ascii_text(value):
    value = html.unescape(re.sub(r'<[^>]*>|\{\\[^}]*\}', '', str(value)))
    value = value.translate(str.maketrans({'£': '#', '’': "'", '“': '"', '”': '"', '–': '-', '—': '-'}))
    return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()


def odd(value):
    value &= 127
    return value | ((1 ^ (value.bit_count() & 1)) << 7)


def row_packet(page, row, text):
    if not 100 <= page <= 899 or not 0 <= row <= 24:
        raise ValueError('Invalid Teletext page/row')
    mag = page // 100 % 8
    return bytes((0x55, 0x55, 0x27, HAM[mag | ((row & 1) << 3)], HAM[row >> 1])) + bytes(
        odd(v) for v in text.encode('ascii', 'replace')[:40].ljust(40))


def page_packets(page, rows, *, subtitle=False, update=0, erase=True):
    """25 rows; subtitle pages have boxed bottom rows and suppressed header.

    Control bits follow VBIT2 Packet::Header / ETS300706: C4 erase, C6 subtitle,
    C7 suppress header, C8 update. Parallel magazines keep 888 independent.
    """
    packet = bytearray(row_packet(page, 0, ''))
    digits = page % 100
    packet[5:13] = bytes(HAM[n] for n in (
        digits % 10, digits // 10, 0, 8 if erase else 0, 0,
        8 if subtitle else 0, (1 if subtitle else 0) | (2 if update & 1 else 0), 0))
    packet[13:] = bytes(odd(v) for v in f'PACE {page:03d} TEXT SERVICE'.encode().ljust(32))
    result = [bytes(packet)]
    for row in range(1, 25):
        text = rows.get(row, '') if isinstance(rows, dict) else (rows[row - 1] if row <= len(rows) else '')
        result.append(row_packet(page, row, text))
    return result


def subtitle_packets(text, revision=0):
    # Box controls are doubled for level-1 receivers. Explicit blank rows clear
    # the previous cue. Normal height avoids relying on TV double-height layout.
    wrapped = textwrap.wrap(ascii_text(text), width=34, break_long_words=True)[:3]
    rows = {22 + i: '\x0b\x0b\x07' + line.center(34) + '\x0a\x0a' for i, line in enumerate(wrapped)}
    # Header + all three possible subtitle rows: small and promptly repeated.
    all_rows = page_packets(888, rows, subtitle=True, update=revision)
    return [all_rows[0], *all_rows[22:25]]


def descriptor_payload():
    # eng, initial magazine1/page100; eng, subtitles magazine8/page888.
    return b'eng\x09\x00eng\x10\x88'


def transport_packet(packets, cc=0):
    """One complete canonical private_stream_1 PES, no pointer_field."""
    if not 1 <= len(packets) <= 3 or any(len(p) != 45 or p[:3] != b'\x55\x55\x27' for p in packets):
        raise ValueError('Expected 1..3 raw Teletext packets')
    payload = b'\x00\x00\x01\xbd\x00\xb2\x84\x00\x24' + b'\xff' * 36 + b'\x10'
    for index, packet in enumerate(packets):
        # Field/line descriptor, framing E4 (MSB first), reverse T42 bytes.
        kind = 3 if HAM.index(packet[3]) & 7 == 0 else 2
        payload += bytes((kind, 44, 0xf0 + index, 0xe4)) + packet[3:].translate(REVERSE)
    payload += (b'\xff\x2c' + b'\xff' * 44) * (3 - len(packets))
    assert len(payload) == 184
    return bytes((0x47, 0x40 | PID >> 8, PID & 255, 0x10 | cc & 15)) + payload


def unpack_pes(data):
    """Extract raw packets from a complete DVB PES (also used for IPTV copy)."""
    if len(data) < 10 or data[:4] != b'\x00\x00\x01\xbd':
        return []
    pos = 9 + data[8]
    if pos >= len(data) or not 0x10 <= data[pos] <= 0x1f:
        return []
    pos += 1
    result = []
    while pos + 2 <= len(data):
        kind, size = data[pos:pos + 2]
        pos += 2
        if pos + size > len(data):
            break
        if kind in (2, 3) and size == 44 and data[pos + 1] == 0xe4:
            result.append(b'\x55\x55\x27' + data[pos + 2:pos + 44].translate(REVERSE))
        pos += size
    return result


def timestamp(value):
    h, m, s = value.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


def srt_cues(lines):
    """Incremental parser: caller supplies a bounded/streaming line iterator."""
    block = []
    for line in lines:
        line = line.strip('\r\n\ufeff')
        if line:
            block.append(line)
            if len(block) > 64:
                block = block[-64:]
            continue
        cue = _srt_block(block)
        if cue:
            yield cue
        block = []
    cue = _srt_block(block)
    if cue:
        yield cue


def _srt_block(block):
    for i, line in enumerate(block):
        match = re.match(r'(\d+:\d{2}:\d{2}[,.]\d+)\s*-->\s*(\d+:\d{2}:\d{2}[,.]\d+)', line)
        if match:
            start, end = map(timestamp, match.groups())
            if 0 <= start < end and end - start <= 3600:
                return Cue(start, end, ascii_text(' '.join(block[i + 1:])))
    return None


class Carousel:
    """Nonblocking output scheduler, capped at 120 TS packets/s.

    Four packets per subtitle update get first opportunity, then information
    pages round-robin. Subtitle copies repeat at 5Hz; full pages are atomic so
    headers cannot interrupt their own magazine's body. No unbounded backlog.
    """
    def __init__(self, pages=None):
        self.pages = pages or [page_packets(100, {2: 'PACE TELETEXT', 4: '100 INDEX    888 SUBTITLES'})]
        self.queue = deque()
        self.pending_subtitle = deque()
        self.page_index = 0
        self.due = 0.
        self.sub_due = 0.
        self.text = None
        self.revision = 0
        self.cc = 0

    def packet(self, when, subtitle='', raw=None):
        if when < self.due:
            return None
        self.due = when + 1 / 120
        if subtitle is None:
            self.pending_subtitle.clear()
            self.text = None
        elif subtitle != self.text:
            self.text = subtitle
            self.revision ^= 1
            self.pending_subtitle = deque(subtitle_packets(subtitle, self.revision))
            self.sub_due = when + .2
        elif when >= self.sub_due and not self.pending_subtitle:
            repeats = subtitle_packets(subtitle, self.revision)
            header = bytearray(repeats[0]);header[8] = HAM[0]
            repeats[0] = bytes(header)  # repeated cue does not erase the page
            self.pending_subtitle.extend(repeats)
            self.sub_due = when + .2
        packets = []
        for _ in range(3):
            if self.pending_subtitle:
                packets.append(self.pending_subtitle.popleft())
            elif raw:
                packets.append(raw.popleft())
            else:
                if not self.queue:
                    self.queue.extend(self.pages[self.page_index % len(self.pages)])
                    self.page_index += 1
                packets.append(self.queue.popleft())
        result = transport_packet(packets, self.cc)
        self.cc = (self.cc + 1) & 15
        return result
