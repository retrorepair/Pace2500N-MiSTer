"""Streaming MPEG-TS PSI/SI framing, independent of firmware addresses."""
PACKET_SIZE = 188


def crc32_mpeg(data):
    crc = 0xffffffff
    for byte in data:
        crc ^= byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x04c11db7 if crc & 0x80000000 else 0)) & 0xffffffff
    return crc


def validate_section(section):
    if len(section) < 3 or len(section) != 3 + ((section[1] & 15) << 8) + section[2]:
        raise ValueError('Section length mismatch')
    # TDT has no CRC; TOT does, despite using short-section syntax.
    if section[1] & 0x80 or section[0] == 0x73:
        if len(section) < 7 or crc32_mpeg(section):
            raise ValueError('Invalid MPEG section CRC')


class SectionAssembler:
    """Accept arbitrary chunks; recover at PUSI; emit sections without CRC filtering.

    Keeping CRC validation separate preserves the boot research probe API.
    Exact duplicate payload packets are ignored. Adaptation-only packets do not
    advance payload continuity. Invalid packets discard only their PID state.
    """
    def __init__(self):
        self.pending = {}
        self.continuity = {}
        self.last_packet = {}
        self.tail = bytearray()
        self.packets = 0
        self.errors = 0
        self.duplicates = 0

    def feed(self, data):
        self.tail.extend(data)
        sections = []

        def append(pid, chunk, allow_new):
            buf = self.pending.setdefault(pid, bytearray())
            for byte in chunk:
                if not buf and (not allow_new or byte == 0xff):
                    return
                buf.append(byte)
                if len(buf) >= 3:
                    size = 3 + ((buf[1] & 15) << 8) + buf[2]
                    if size > 4096:
                        self.errors += 1
                        buf.clear()
                        return
                    if len(buf) == size:
                        sections.append((pid, bytes(buf)))
                        buf.clear()
                        if not allow_new:
                            return

        position = 0
        while len(self.tail) - position >= PACKET_SIZE:
            if self.tail[position] != 0x47:
                self.errors += 1
                position += 1
                continue
            p = bytes(self.tail[position:position + PACKET_SIZE])
            position += PACKET_SIZE
            self.packets += 1
            pid = ((p[1] & 31) << 8) | p[2]
            if pid == 0x1fff:
                continue
            afc = (p[3] >> 4) & 3
            start = 4
            discontinuity = False
            invalid = bool(p[1] & 0x80 or p[3] & 0xc0 or afc == 0)
            if afc & 2:
                start = 5 + p[4]
                invalid |= start > 188 or (afc == 2 and start != 188)
                discontinuity = bool(p[4] and p[5] & 0x80)
            if invalid:
                self.errors += 1
                self.pending.pop(pid, None)
                self.continuity.pop(pid, None)
                continue
            if discontinuity:
                self.pending.pop(pid, None)
                self.continuity.pop(pid, None)
            if not afc & 1 or start == 188:
                continue
            cc = p[3] & 15
            previous = self.continuity.get(pid)
            if previous == cc and self.last_packet.get(pid) == p:
                self.duplicates += 1
                continue
            if previous is not None and cc != (previous + 1) & 15:
                self.errors += 1
                self.pending.pop(pid, None)
            self.continuity[pid] = cc
            self.last_packet[pid] = p
            payload = p[start:]
            if p[1] & 0x40:
                pointer = payload[0]
                if pointer > len(payload) - 1:
                    self.errors += 1
                    self.pending.pop(pid, None)
                    continue
                if self.pending.get(pid):
                    append(pid, payload[1:1 + pointer], False)
                if self.pending.get(pid):
                    self.errors += 1
                self.pending[pid] = bytearray()
                append(pid, payload[1 + pointer:], True)
            elif self.pending.get(pid):
                append(pid, payload, False)
        del self.tail[:position]
        return sections


class Packetizer:
    """One section per PUSI boundary; persistent per-PID continuity counters."""
    def __init__(self):
        self.continuity = {}

    def section(self, pid, section):
        if not 0 <= pid < 0x1fff:
            raise ValueError('Invalid section PID')
        validate_section(section)
        first = True
        output = bytearray()
        while section:
            cc = self.continuity.get(pid, 0)
            self.continuity[pid] = (cc + 1) & 15
            prefix = b'\x00' if first else b''
            chunk, section = section[:184 - len(prefix)], section[184 - len(prefix):]
            output += bytes((0x47, (pid >> 8) | (0x40 if first else 0), pid & 255, 0x10 | cc))
            output += prefix + chunk + b'\xff' * (184 - len(prefix) - len(chunk))
            first = False
        return bytes(output)

    def null(self):
        cc = self.continuity.get(0x1fff, 0)
        self.continuity[0x1fff] = (cc + 1) & 15
        return bytes((0x47, 0x1f, 0xff, 0x10 | cc)) + b'\xff' * 184
