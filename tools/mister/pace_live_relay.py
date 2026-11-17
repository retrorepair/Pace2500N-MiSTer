#!/usr/bin/env python3
"""Pace 2500N live relay -- runs on the MiSTer's ARM (HPS) side.

Keeps a ring file in RAM (/tmp, tmpfs) that the core mounts as image slot 0
(launcher Pace2500N_V060_Live.mgl). The core writes a status block into the
file (via Main_MiSTer) with the A/V PIDs the firmware has routed to its
decoder -- that is how the receiver "tunes". The relay asks the PC playout
server (tools/pace_playout.py) for that service and copies the stream it
sends into the ring, never more than the ring holds ahead of the core.

Nothing is requested while the core is not running (its status sequence
stops), and every change of tuning ends the previous request, so the PC only
transcodes what the box is actually watching.

The transponder: the firmware's MPEG manager (guest RAM 0x80163198) holds the tuned
frequency, BCD as in the NIT, at +0x1C. The relay reads it from the FPGA's DDR3 window
(guest RAM at 0x30000000) and sends it with each request (freq=), so a retune -- e.g. the
TV Guide tuning the home transponder -- reaches the playout like a PID change does.

File layout (big-endian; must match rtl/pace_ts_stream.sv):
  0     47 1F FE 10 "PACELIVE" session(u32) written(u32) ring_bytes(u32)
  24    "AV1" flags(u8): bit 0 = EPG mode, bit 1 = home background audio active
  512   "PACESTAT" session(u32) read_pos(u32) video(u16) audio(u16) seq(u32)
        played(u32) underruns(u32)                      -- written by the core
  544   "LB1" flags(u8): bit 0 = fit widescreen into the 4:3 picture
  1024  ring data: session byte n at 1024 + n % ring_bytes

Usage: pace_live_relay.py [--server HOST:PORT] [--file /tmp/pace_live.ts]
       [--ring-mib 8] [--config /media/fat/linux/pace/relay.ini]
"""
import argparse, configparser, fcntl, mmap, os, select, socket, struct, sys, time

CHUNK = 8192
HOME_FREQ = 0x01177800
RADIO_PIDS = range(0x0700, 0x0764)  # numbered services 800–899 (pace_channels.RadioStation)
HEAD = 1024
LOG = '/tmp/pace_live_relay.log'


def log(msg):
    line = time.strftime('%H:%M:%S ') + msg
    print(line, flush=True)
    try:
        with open(LOG, 'a') as f:
            f.write(line + '\n')
    except OSError:
        pass


class GuestRAM:
    """The core's guest RAM, read-only, from the HPS: DDR3 0x30000000 + physical address."""
    TUNED_FREQ = 0x801631B4          # MPEG manager 0x80163198 + 0x1C: tuned frequency (BCD)
    EPG_MODE = 0x80161D50            # AV manager dispatch cases 6/7, pointer at 0x80056258
    BACKGROUND_MUSIC = 0x80477228    # Guide o-code global for SSBM

    def __init__(self):
        try:
            fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
            try:
                self.m = mmap.mmap(fd, 16 << 20, mmap.MAP_SHARED, mmap.PROT_READ, offset=0x30000000)
            finally:
                os.close(fd)
        except OSError as e:
            log(f'guest RAM not readable ({e}): transponder not reported')
            self.m = None

    def freq(self):
        """Tuned frequency as BCD (0x01177800 = 11778.00 MHz), None if not a Ku-band value."""
        if not self.m:
            return None
        f = struct.unpack_from('>I', self.m, self.TUNED_FREQ & 0xffffff)[0]
        ok = all((f >> s & 0xf) < 10 for s in range(0, 32, 4)) and 0x01070000 <= f <= 0x01280000
        return f if ok else None

    def word(self, addr):
        return struct.unpack_from('>I', self.m, addr & 0xffffff)[0] if self.m else 0


class Ring:
    def __init__(self, path, ring):
        self.ring = ring
        self.fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        os.ftruncate(self.fd, HEAD + ring)
        self.session = int(time.time()) & 0xffffffff   # unique across relay restarts
        self.written = 0
        self.av_flags = 0
        os.pwrite(self.fd, bytes(512), 512)              # no stale status
        self.header()

    def header(self):
        os.pwrite(self.fd, b'\x47\x1f\xfe\x10PACELIVE' + struct.pack('>III', self.session,
                  self.written & 0xffffffff, self.ring) + b'AV1' + bytes((self.av_flags,)), 0)

    def set_av(self, epg, music):
        flags = int(epg) | (int(music) << 1)
        if flags != self.av_flags:
            self.av_flags = flags
            self.header()

    def new_session(self):
        self.session = (self.session + 1) & 0xffffffff
        self.written = 0
        self.header()

    def status(self):
        b = os.pread(self.fd, 36, 512)
        if b[:8] != b'PACESTAT':
            return None
        session, read_pos, video, audio, seq, played, underruns = struct.unpack('>IIHHIII', b[8:32])
        return dict(session=session, read_pos=read_pos, video=video, audio=audio, seq=seq,
                    played=played, underruns=underruns, letterbox=b[32:35] == b'LB1' and bool(b[35] & 1))

    def space(self, st):
        core = st['read_pos'] if st and st['session'] == self.session else 0
        return self.ring - ((self.written - core) & 0xffffffff)

    def put(self, chunk):
        off = self.written % self.ring
        os.pwrite(self.fd, chunk, HEAD + off)            # data first, then the header
        self.written += len(chunk)
        self.header()


def query(video, audio, freq, letterbox=False):
    return (f'video=0x{video:04x}&audio=0x{audio:04x}' + (f'&freq={freq:08x}' if freq else '')
            + ('&letterbox=1' if letterbox else ''))


class Upstream:
    """One HTTP request to the playout server for one tuning."""
    def __init__(self, server, video, audio, freq=None, letterbox=False):
        host, port = server.rsplit(':', 1)
        self.sock = socket.create_connection((host, int(port)), timeout=2)
        try:
            self.sock.sendall(f'GET /tune?{query(video, audio, freq, letterbox)} HTTP/1.0\r\n'
                              f'Host: {host}\r\n\r\n'.encode())
            head = b''
            while b'\r\n\r\n' not in head:
                part = self.sock.recv(4096)
                if not part or len(head) > 16384:
                    raise ConnectionError('incomplete playout response')
                head += part
            head, self.pending = head.split(b'\r\n\r\n', 1)
            status, *headers = head.split(b'\r\n')
            if b' 200 ' not in status + b' ':
                raise ConnectionError(status.decode(errors='replace'))
            self.service = next((line.split(b':', 1)[1].strip() for line in headers
                                 if line.lower().startswith(b'x-pace-service:')), None)
            self.sock.setblocking(False)
        except BaseException:
            self.sock.close()
            raise
        self.pending = bytearray(self.pending)
        self.eof = False
        self.last_data = time.monotonic()

    def fill(self, limit):
        if len(self.pending) >= limit:
            self.last_data = time.monotonic()   # backpressure from the FPGA ring
        while len(self.pending) < limit and not self.eof:
            try:
                part = self.sock.recv(65536)
            except BlockingIOError:
                if time.monotonic() - self.last_data > 25:
                    log('playout stream stalled')
                    self.eof = True
                return
            except OSError:          # reset / aborted: treat as the end of the stream
                self.eof = True
                return
            if not part:
                self.eof = True
                return
            self.pending += part
            self.last_data = time.monotonic()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='/media/fat/linux/pace/relay.ini')
    ap.add_argument('--server')
    ap.add_argument('--file', default='/tmp/pace_live.ts')
    ap.add_argument('--ring-mib', type=int, default=8)
    a = ap.parse_args()
    server = a.server
    if not server and os.path.exists(a.config):
        cfg = configparser.ConfigParser()
        cfg.read(a.config)
        server = cfg.get('relay', 'server', fallback=None)
    if not server:
        sys.exit('no playout server: pass --server HOST:PORT or set [relay] server= in ' + a.config)
    # one relay per ring file: a second one would fight over the header
    lock = open(a.file + '.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit('another relay is already running for ' + a.file)
    ring = Ring(a.file, a.ring_mib << 20)
    guest = GuestRAM()
    log(f'relay up: {a.file} ({a.ring_mib} MiB ring), playout server {server}')
    up = None
    tuned = None                 # (video, audio) currently requested, None = nothing
    want = None; want_since = 0.0
    last_seq = None; alive_at = 0.0
    retry_at = 0.0
    while True:
        try:
            up, tuned, want, want_since, last_seq, alive_at, retry_at = step(
                ring, guest, server, up, tuned, want, want_since, last_seq, alive_at, retry_at)
        except Exception as e:       # never die: the box would starve
            log(f'relay error: {e!r}; recovering')
            if up:
                up.close()
            up, tuned = None, None
            ring.set_av(False, False)
            ring.new_session()
            time.sleep(1)


def step(ring, guest, server, up, tuned, want, want_since, last_seq, alive_at, retry_at):
    now = time.monotonic()
    st = ring.status()
    restarted = st and last_seq is not None and (st['seq'] - last_seq) & 0x80000000
    if st and st['seq'] != last_seq:
        last_seq, alive_at = st['seq'], now
    alive = st is not None and now - alive_at < 3.0
    freq = guest.freq() if alive else None
    epg = alive and guest.word(guest.EPG_MODE) == 1
    music_enabled = epg and guest.word(guest.BACKGROUND_MUSIC) == 1
    if not alive:
        current = None
    elif freq == HOME_FREQ or (freq is None and (epg or not st['video'] & 0x4000)):
        # The same home transport is used on every EPG screen, even when the
        # firmware takes the audio PID off its own route between menus.
        # The server also defaults to this transport during initial acquisition.
        # Retain the stream when the guest first publishes the home frequency.
        current = (0x1fff, 0x4288, HOME_FREQ, False)
    else:
        video = st['video'] if st['video'] & 0x4000 and not epg else 0x1fff
        radio = st['audio'] & 0x4000 and (st['audio'] & 0x1fff) in RADIO_PIDS and not epg
        audio = st['audio'] if video == 0x1fff and radio else 0x1fff
        current = (video, audio, freq, video != 0x1fff and st['letterbox'])
    if current != want:
        want, want_since = current, now

    if restarted or (want != tuned and (epg or want is None or now - want_since >= 0.15)):
        if up:
            up.close()
            up = None
        tuned = want
        ring.set_av(epg, False)
        ring.new_session()
        retry_at = 0
        if tuned:
            log(f'tuned: video {tuned[0]:04x} audio {tuned[1]:04x} freq {tuned[2] or 0:08x}'
                + (' letterbox' if tuned[3] else '')
                + f' -> session {ring.session:08x}')
        else:
            log('core not running: nothing requested')

    ring.set_av(epg, bool(music_enabled and up and up.service == b'music@0' and tuned == want))
    if tuned is not None and up is None and now >= retry_at:
        try:
            up = Upstream(server, *tuned)
        except OSError as e:
            log(f'playout server: {e}; retrying in 2 s')
            retry_at = time.monotonic() + 2
    if up:
        up.fill(4 * CHUNK)
        while len(up.pending) >= CHUNK and ring.space(st) >= CHUNK:
            ring.put(bytes(up.pending[:CHUNK]))
            del up.pending[:CHUNK]
        if up.eof and len(up.pending) < CHUNK:
            log('playout stream ended; requesting again')
            up.close()
            up = None
            ring.set_av(epg, False)
            ring.new_session()
            retry_at = now + 0.5
    if up and len(up.pending) < 4 * CHUNK:
        select.select([up.sock], [], [], 0.005)
    else:
        time.sleep(0.005)
    return up, tuned, want, want_since, last_seq, alive_at, retry_at


if __name__ == '__main__':
    main()
