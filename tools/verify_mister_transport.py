#!/usr/bin/env python3
"""Read-only physical verification of v048 TS upload and guest section rings.

Run on MiSTer after the MGL finished loading. No /dev/mem writes or CPU/RAM
interventions. The guest remains live, so the RAM readback is not atomic.
"""
import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path
from pace_transport import crc32_mpeg, validate_section


def scan_ring(data):
    """Find complete CRC-protected records despite a wrapped ring base."""
    doubled = data + data
    records = []
    for offset, table in enumerate(data):
        if table not in (0x40, 0x42, 0x4a, 0x73, 0xa0, 0xa1, 0xa2, 0xa3, 0xc1):
            continue
        size = 3 + ((doubled[offset + 1] & 15) << 8) + doubled[offset + 2]
        if not 8 <= size <= 4096 or doubled[offset + size] != 0:
            continue
        section = doubled[offset:offset + size]
        try:
            validate_section(section)
        except ValueError:
            continue
        if crc32_mpeg(section) == 0:
            records.append(dict(offset=f'{offset:04X}', table=f'{table:02X}', bytes=size,
                                extension=section[3:5].hex().upper() if section[1] & 128 else None))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('transport', type=Path)
    parser.add_argument('--ram-output', type=Path)
    parser.add_argument('--skip-ring-scan', action='store_true', help='Capture quickly; omit circular CRC census')
    args = parser.parse_args()
    original = args.transport.read_bytes()
    if not original or len(original) > 1048576 or len(original) % 188:
        raise ValueError('Invalid bounded TS replay file')
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        length = (len(original) + 4095) & ~4095
        with mmap.mmap(fd, length, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x33000000) as region:
            received = bytes(region[:len(original)])
        with mmap.mmap(fd, 16 * 1024 * 1024, flags=mmap.MAP_SHARED,
                       prot=mmap.PROT_READ, offset=0x30000000) as region:
            ram = bytes(region)
    finally:
        os.close(fd)
    if received != original:
        raise ValueError('FPGA replay DDR differs from the selected TS file')
    baseline = Path('/media/fat/games/Pace2500N_GUIDE/RAM.bin').read_bytes()
    word = lambda data, at: int.from_bytes(data[at:at + 4], 'big')
    rings = []
    for channel in (20, 21, 22, 23, 24):
        address = 0x7a0000 + channel * 0x3000
        record = 0x142d34 + channel * 20
        size = 3 + ((ram[address + 1] & 15) << 8) + ram[address + 2]
        isr_pointer = word(ram, 0x107588 + channel * 4)
        valid = False
        if isr_pointer and 4 <= size <= 4096:
            try:
                section = ram[address:address + size]
                validate_section(section)
                valid = crc32_mpeg(section) == 0
            except ValueError:
                pass
        current = [word(ram, record + i * 4) for i in range(5)]
        previous = [word(baseline, record + i * 4) for i in range(5)]
        complete = [] if args.skip_ring_scan else scan_ring(ram[address:address + 0x3000])
        rings.append(dict(channel=channel, first_table=f'{ram[address]:02X}', first_section_crc_valid=valid,
                          guest_isr_write_pointer=f'{isr_pointer:08X}',
                          descriptor=[f'{n:08X}' for n in current],
                          descriptor_changed_from_checkpoint=current != previous,
                          complete_crc_valid_records=None if args.skip_ring_scan else len(complete), record_samples=complete[:3]))
    result = dict(live_non_atomic_readback=True, memory_writes=False,
                  circular_crc_scan_performed=not args.skip_ring_scan,
                  ring_base_may_contain_wrapped_payload=True,
                  transport_file=str(args.transport), bytes=len(original),
                  transport_ddr_sha256=hashlib.sha256(received).hexdigest(), rings=rings,
                  firmware_state={
                      'frontend_state_800fcdc4': word(ram, 0x0fcdc4),
                      'frontend_flag_80105c00': word(ram, 0x105c00),
                      'av_active_byte_80161d3c': ram[0x161d3c],
                      'av_selection_80161d40': f'{word(ram, 0x161d40):08X}',
                      'checkpoint_default_80054f84': f'{word(ram, 0x054f84):08X}',
                      'checkpoint_readiness_80430a28': word(ram, 0x430a28),
                  },
                  decoded_text_locations={text: [f'{n:08X}' for n in find_all(ram, text.encode('ascii'))]
                                          for text in ('LOCAL TEST ONE', 'LOCAL TEST TWO', 'NEXT TEST ONE', 'NEXT TEST TWO')})
    if args.ram_output:
        args.ram_output.write_bytes(ram)
    print(json.dumps(result, indent=2))


def find_all(data, text):
    position = -1
    while True:
        position = data.find(text, position + 1)
        if position < 0:
            return
        yield position


if __name__ == '__main__':
    main()
