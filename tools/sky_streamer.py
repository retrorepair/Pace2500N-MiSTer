"""Deterministic PC-side SI replay builder/validator; binary stdout stays clean.

No implicit downloads, scraped schedules, fake media URLs, or CPU emulation.
The first FPGA transport contract is a packet-aligned file at MGL index 3.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from pace_si import diagnostic_tables, with_crc
from pace_transport import Packetizer, SectionAssembler, validate_section


def inspect(data):
    if not data or len(data) % 188 or any(data[i] != 0x47 for i in range(0, len(data), 188)):
        raise ValueError('Input must contain aligned, complete 188-byte TS packets')
    assembler = SectionAssembler()
    tables = {}
    for pid, section in assembler.feed(data):
        validate_section(section)
        key = f'{pid:04X}:{section[0]:02X}'
        tables[key] = tables.get(key, 0) + 1
    if assembler.errors or any(assembler.pending.values()):
        raise ValueError(f'Incomplete/discontinuous section stream: {assembler.errors} errors')
    return dict(bytes=len(data), packets=len(data) // 188, tables=tables,
                sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    fixture = sub.add_parser('fixture', help='Build a labelled synthetic SI-only carousel')
    fixture.add_argument('--utc', default='2002-09-01T12:00:00+00:00')
    fixture.add_argument('--seconds', type=int, default=4)
    fixture.add_argument('--output', required=True, help='TS file, or - for binary stdout')
    fixture.add_argument('--huffman-ram', type=Path, help='Operator initialized RAM: add native OpenTV rows/titles')
    fixture.add_argument('--full-day', action='store_true', help='Cover all four title blocks with hourly synthetic programmes')
    fixture.add_argument('--index', action='store_true', help='Add C1 alphabet/genre indices, paced after title sections')
    fixture.add_argument('--index-updates', action='store_true', help='Cycle index versions to exercise late subscriber notifications')
    fixture.add_argument('--table-period-ms', type=int, default=200,
                         help='SI/title wave period, a multiple of 200ms (default 200)')
    fixture.add_argument('--channel', action='append', help='Channel name (repeatable); default TEST ONE/TWO')
    fixture.add_argument('--loop-title', help='Title of one programme repeated back to back all day')
    fixture.add_argument('--loop-seconds', type=int, help='Length of the looped programme (even seconds)')
    fixture.add_argument('--loop-anchor', default='18:00', help='HH:MM (UTC) at which one showing starts')
    fixture.add_argument('--clock-once', action='store_true',
                         help='Send the fixed diagnostic TOT only once per replay file')
    check = sub.add_parser('inspect', help='Validate a packet-aligned PSI/SI transport')
    check.add_argument('input', type=Path)
    args = parser.parse_args()
    if args.command == 'inspect':
        print(json.dumps(inspect(args.input.read_bytes()), indent=2))
        return
    if not 1 <= args.seconds <= 8:
        parser.error('Replay fixture must be 1..8 seconds (fits 1 MiB at 1 Mbit/s)')
    if args.table_period_ms < 200 or args.table_period_ms % 200 or args.table_period_ms > args.seconds * 1000:
        parser.error('--table-period-ms must be a multiple of 200 within the file duration')
    when = datetime.fromisoformat(args.utc)
    codec = None
    if args.huffman_ram:
        from pace_huffman import FirmwareHuffman
        codec = FirmwareHuffman.from_file(args.huffman_ram)
    if (args.full_day or args.index) and not codec:
        parser.error('--full-day/--index require --huffman-ram')
    if args.index_updates and not args.index:
        parser.error('--index-updates requires --index')
    loop = None
    if args.loop_title:
        if not args.loop_seconds or args.loop_seconds % 2:
            parser.error('--loop-title needs an even --loop-seconds')
        hh, mm = map(int, args.loop_anchor.split(':'))
        loop = (args.loop_title, args.loop_seconds, hh * 3600 + mm * 60)
        if not codec:
            parser.error('--loop-title requires --huffman-ram')
    tables = diagnostic_tables(when, codec, args.full_day, args.index, channels=args.channel, looped=loop)
    indices = [(pid, section) for pid, section in tables if section[0] == 0xc1]
    tables = [(pid, section) for pid, section in tables if section[0] != 0xc1]
    packetizer = Packetizer()
    data = bytearray()
    # Each wave retains a fixed byte budget. Table periods can be reduced for
    # CPU/notification-pressure diagnostics without changing the FPGA byte rate.
    # Null packets carry no PCR. This fixed diagnostic clock does not advance.
    for tick in range(args.seconds * 5):
        start = len(data)
        if tick % (args.table_period_ms // 200) == 0:
            for pid, section in tables:
                if section[0] != 0x73 or not args.clock_once or tick == 0:
                    data += packetizer.section(pid, section)
        if indices:
            # Leave guest time to drain/decode titles before references arrive.
            # The update diagnostic covers every head twice per file. A late
            # subscriber then sees a new DVB version, rather than only exact
            # duplicates of a table sent before it registered its callback.
            while len(data) - start < 80 * 188:
                data += packetizer.null()
            count = 4 if args.index_updates else 2
            for n in range(count):
                cursor = tick * count + n
                pid, section = indices[cursor % len(indices)]
                if args.index_updates:
                    version = (cursor // len(indices)) & 31
                    body = bytearray(section[:-4]);body[5] = 0xc1 | version << 1
                    section = with_crc(body)
                data += packetizer.section(pid, section)
        while len(data) - start < 133 * 188:
            data += packetizer.null()
    result = inspect(data)
    result.update(kind='synthetic SI/OpenTV diagnostic' if codec else 'synthetic SI-only diagnostic', utc=when.isoformat(),
                  bitrate=1000000, clock='fixed, GMT descriptor',
                  firmware_execution='FPGA', opentv_titles=bool(codec), media=False)
    result.update(full_day=args.full_day, index=args.index, index_updates=args.index_updates)
    result.update(table_period_ms=args.table_period_ms, clock_once_per_file=args.clock_once)
    if args.output == '-':
        sys.stdout.buffer.write(data)
    else:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), file=sys.stderr)


if __name__ == '__main__':
    main()
