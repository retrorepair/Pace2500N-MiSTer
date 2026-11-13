"""Small, deterministic DVB SI encoder for labelled synthetic replay fixtures.

This is not a historical listings database or a generic OpenTV title encoder.
Private descriptor field layouts follow the same-ROM RE recorded in
re/TRANSPORT_INTEGRATION.md; standard DVB tables are encoded independently.
"""
from datetime import datetime, timezone
from pace_transport import crc32_mpeg


def u16(n):
    return n.to_bytes(2, 'big')


def loop(data):
    if len(data) > 4095:
        raise ValueError('Descriptor loop too long')
    return u16(0xf000 | len(data)) + data


def descriptor(tag, data):
    if len(data) > 255:
        raise ValueError('Descriptor too long')
    return bytes((tag, len(data))) + data


def with_crc(data):
    return data + crc32_mpeg(data).to_bytes(4, 'big')


def long_section(table, extension, payload, version=0):
    length = len(payload) + 9
    if length > 1021 or not 0 <= version <= 31:
        raise ValueError('Long section exceeds DVB SI bounds')
    return with_crc(bytes((table,)) + u16(0xb000 | length) + u16(extension)
                    + bytes((0xc1 | version << 1, 0, 0)) + payload)


def bcd(n):
    if not 0 <= n <= 99:
        raise ValueError('BCD out of range')
    return n // 10 * 16 + n % 10


def dvb_utc(when):
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError('UTC encoding requires an aware datetime')
    when = when.astimezone(timezone.utc)
    mjd = (when.date() - datetime(1858, 11, 17).date()).days
    return u16(mjd) + bytes(map(bcd, (when.hour, when.minute, when.second)))


def tot(when):
    # Fixed GMT diagnostic clock, explicitly unrelated to live wall-clock/BST.
    offset = b'GBR\x02\x00\x00' + dvb_utc(when) + b'\x00\x00'
    body = dvb_utc(when) + loop(descriptor(0x58, offset))
    return with_crc(b'\x73' + u16(0x7000 | (len(body) + 4)) + body)


def title_section(table, listing, mjd, events, codec):
    records = bytearray()
    for event_id, start, duration, title in events:
        if start % 2 or duration % 2 or not 0 <= start < 86400 or not 0 < duration <= 86400:
            raise ValueError('OpenTV times need positive durations and even seconds')
        body = u16(start // 2) + u16(duration // 2) + b'\x00\x00\x00' + codec.encode(title)
        desc = descriptor(0xb5, body)
        # packet_length counts AFTER the four-byte event/length header.
        records += u16(event_id) + u16(0xf000 | len(desc)) + desc
    return long_section(table, listing, u16(mjd) + records)


def summary_section(table, listing, mjd, summaries):
    """OpenTV summary (synopsis) section, tables 0xA8-0xAB on PIDs 0x40-0x47: the title
    section's addressing and record framing, one descriptor 0xB9 per event carrying the
    Huffman-coded synopsis. summaries: [(event_id, coded_bytes)]."""
    records = bytearray()
    for event_id, coded in summaries:
        desc = descriptor(0xb9, coded)
        records += u16(event_id) + u16(0xf000 | len(desc)) + desc
    return long_section(table, listing, u16(mjd) + records)


def loop_events(title, duration, anchor):
    """One programme repeated back to back across the day, a showing starting at
    `anchor` seconds; the first entry is the tail of the showing before midnight."""
    if duration % 2 or anchor % 2 or duration <= 0:
        raise ValueError('loop duration/anchor must be positive even seconds')
    first = anchor % duration
    events = [(0, first)] if first else []
    start = first
    while start < 86400:
        events.append((start, duration))
        start += duration
    return [(start, length, title) for start, length in events]


def diagnostic_tables(when, codec=None, full_day=False, with_index=False, channels=None, looped=None, es=None,
                      music=None, music_linkage=False):
    """Synthetic test services; no claim that these were broadcast.

    channels: optional list of channel names (default TEST ONE / TEST TWO).
    looped: optional (title, duration_seconds, anchor_seconds) schedule used for
    every channel instead of the hourly test programmes.
    es: optional (video_pid, audio_pid). The first service's PMT then lists an
    MPEG-2 video stream (stream_type 2, also the PCR PID) and an MPEG-1 Layer II
    audio stream (stream_type 3); the caller muxes the matching PES.
    music: optional (service_id, audio_pid): an audio-only digital radio service
    named "EPG Background Audio" on this transport (SDT, PAT, PMT and the BAT's
    service list; not a numbered channel in the line-up). music_linkage points
    the BAT's 0x91 guide linkage at it instead of the first TV service."""
    names = channels or ['TEST ONE', 'TEST TWO']
    services = [(1001 + i, 3000 + i, 101 + i, name.encode()) for i, name in enumerate(names)]
    radio = [music] if music else []
    namespace = bytes.fromhex('5f0400000002')
    service_list = descriptor(0x41, b''.join(u16(sid) + b'\x01' for sid, *_ in services)
                              + b''.join(u16(sid) + b'\x02' for sid, _ in radio))
    # 11778 MHz, 28.2E, vertical DVB-S, 27.5 Msym/s, FEC 2/3.
    satellite = descriptor(0x43, bytes.fromhex('011778000282a102750002'))
    transport = u16(0) + u16(0x20)
    nit = long_section(0x40, 0x20, loop(descriptor(0x40, b'PACE DIAGNOSTIC'))
                       + loop(transport + loop(satellite + service_list)))
    sdt_body = u16(0x20) + b'\xff'
    for sid, _, _, name in services:
        desc = namespace + descriptor(0x48, b'\x01\x04TEST' + bytes((len(name),)) + name)
        title = looped[0] if looped else f'LOCAL TEST {"ONE" if sid == 1001 else "TWO"}'
        row_text = codec.encode(title) if codec else b''
        # At8=0 honestly announces no current listing in the SI-only fixture;
        # the title fixture supplies matching row text plus native B5 events.
        desc += descriptor(0xb2, bytes((1 if codec else 0, 0, 3 << 5)) + row_text)
        sdt_body += u16(sid) + b'\xfc' + u16(0x8000 | len(desc)) + desc
    for sid, _ in radio:
        name = b'EPG Background Audio'
        desc = namespace + descriptor(0x48, b'\x02\x05BSkyB' + bytes((len(name),)) + name)
        sdt_body += u16(sid) + b'\xfc' + u16(0x8000 | len(desc)) + desc
    sdt = long_section(0x42, 0, sdt_body)
    linkage = descriptor(0x4a, transport + u16(music[0] if music and music_linkage else 1001) + b'\x91')
    lineup = b'\xff\xff' + b''.join(u16(sid) + b'\x01' + u16(listing) + b'\x00\x00'
                                      + u16(number << 4 | 6) for sid, listing, number, _ in services)
    bat_desc = namespace + descriptor(0xb1, lineup) + service_list + linkage
    bat = long_section(0x4a, 0x1000, loop(descriptor(0x47, b'PACE TEST') + linkage)
                       + loop(transport + loop(bat_desc)))
    pat = long_section(0x00, 0, b''.join(u16(sid) + u16(0xe000 | (0x1000 + i))
                                       for i, (sid, *_) in enumerate(services))
                       + b''.join(u16(sid) + u16(0xe000 | (0x1100 + i)) for i, (sid, _) in enumerate(radio)))
    # There are no elementary streams in this SI-only fixture. Do not advertise
    # imaginary MPEG decoders or fixed audio/video PIDs.
    def pmt_body(i):
        if es and i == 0:
            video, audio = es
            return (u16(0xe000 | video) + b'\xf0\x00'
                    + b'\x02' + u16(0xe000 | video) + b'\xf0\x00'
                    + b'\x03' + u16(0xe000 | audio) + b'\xf0\x00')
        return b'\xff\xff\xf0\x00'
    pmts = [(0x1000 + i, long_section(0x02, sid, pmt_body(i)))
            for i, (sid, *_) in enumerate(services)]
    # Radio service: MPEG-1 Layer II audio only; the audio PID also carries the PCR.
    pmts += [(0x1100 + i, long_section(0x02, sid, u16(0xe000 | pid) + b'\xf0\x00'
                                       + b'\x03' + u16(0xe000 | pid) + b'\xf0\x00'))
             for i, (sid, pid) in enumerate(radio)]
    tables = [(0x14, tot(when)), (0x10, nit), (0x11, sdt), (0x11, bat), (0, pat)] + pmts
    if codec:
        mjd = int.from_bytes(dvb_utc(when)[:2], 'big')
        utc = when.astimezone(timezone.utc)
        current_start = (utc.hour * 3600 + utc.minute * 60 + utc.second) // 1800 * 1800
        index_events = []
        for i, (_, listing, _, _) in enumerate(services):
            name = 'ONE' if i == 0 else 'TWO'
            events = [(i * 100 + 1, current_start - 1800, 1800, f'PREVIOUS TEST {name}'),
                      (i * 100 + 2, current_start, 1800, f'LOCAL TEST {name}'),
                      (i * 100 + 3, current_start + 1800, 1800, f'NEXT TEST {name}')]
            if looped:
                events = [(i * 100 + n + 1, start, length, text)
                          for n, (start, length, text) in enumerate(loop_events(*looped))]
            elif full_day:
                events = [(i * 100 + hour + 1, hour * 3600, 3600,
                           f'LOCAL TEST {name}' if hour == utc.hour else f'TEST {name} {hour:02d}:00')
                          for hour in range(24)]
            groups = {}
            for event in events:
                if 0 <= event[1] < 86400:
                    groups.setdefault(event[1] // 21600, []).append(event)
                    index_events.append((listing, event))
            # Low table bits select a six-hour block. The measured A3/FE rule
            # accepts A2/A3; noon records belong in A2, not simply the literal
            # A3 in the mask. Match-unit acceptance alone is not display proof.
            for block, group in groups.items():
                tables.append((0x30 | (mjd & 7), title_section(0xa0 | block, listing, mjd, group, codec)))
        if with_index:
            # Measured C1 wire layout: listing ID, packed flags, selector,
            # five data bytes; event ID occupies data[1:3]. These are broadcast
            # references, not guest-memory records or fabricated UI objects.
            def index_record(listing, event):
                return u16(listing) + b'\x0f\xc0\x00' + u16(event[0]) + b'\x00\x00'
            for letter in range(ord('A'), ord('Z') + 1):
                payload = b''.join(index_record(listing, event) for listing, event in index_events
                                   if event[3][0].upper() == chr(letter))
                tables.append((0x52, long_section(0xc1, letter, payload)))
            for genre in (0, 3):
                for block in range(4):
                    payload = b''.join(index_record(listing, event) for listing, event in index_events
                                       if event[1] // 21600 == block)
                    tables.append((0x52, long_section(0xc1, 0x100 | block << 6 | genre, payload)))
    return tables
