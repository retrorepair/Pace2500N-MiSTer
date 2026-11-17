#!/usr/bin/env python3
"""Pace 2500N playout server (PC side): on-demand transcoding for the MiSTer.

  pace_playout.py LINEUP.json [--port 8250]

The MiSTer relay (tools/mister/pace_live_relay.py) asks for
  GET /tune?video=0xVVVV&audio=0xAAAA
with the demux routing registers the firmware wrote when it tuned. If the
video PID belongs to a channel in the line-up, the server works out what that
channel is showing right now, transcodes it from its source with ffmpeg
(MPEG-2 720x576i + MPEG-1 Layer II 48 kHz, the formats the box decodes) and
sends it as a 6.25 Mbit/s transport stream with the line-up's guide data
woven in. The home transponder carries the full guide and background audio
when configured. It retains its guide and service map without an audio file.

Nothing is transcoded unless the box asks: when the relay disconnects
(channel change, core stopped) the transcode stops at once. The only buffer is
the one being played from.

Each schedule item (programme part, advert/continuity spot) is one ffmpeg run;
at every item boundary the server re-reads the schedule at the position the
box will have reached (start time + bytes sent / rate), so the picture stays
locked to the guide's clock however long it runs.

GET /           status page (what is on, what is being streamed)
GET /now.json   the same as JSON
"""
import argparse, json, os, queue, select, socket, subprocess, sys, tempfile, threading, time
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pace_channels import (RATE, RadioStation, LiveChannel, load_radio, load_settings, load_lineup, read_lineup, redact,
                           lineup_tables, carousel,  # noqa: E402
                           MUSIC_PID, MUSIC_PMT, MUSIC_SID, HOME_TSID, CHAN_TSID, transport_of)
from pace_radio import RadioMetadata

P = 188
NULL = bytes([0x47, 0x1f, 0xff, 0x10]) + b'\xff' * 184
VIDEO_KBPS, AUDIO_KBPS = 4300, 192
SI_RATE = 125000                # carousel byte rate (1 Mbit/s)
CHUNK_PACKETS = 348
# The 2002 reference's channel excerpts measured about -24 LUFS. Keep the
# Guide 10 LU below TV, with room for the MP2 encoder's peak overshoot.
TV_LUFS, GUIDE_LUFS, TRUE_PEAK = -24, -34, -3
STEREO_48K = 'aresample=48000,aformat=channel_layouts=stereo'


def normalised_audio(target):
    return f'{STEREO_48K},loudnorm=I={target}:TP={TRUE_PEAK}:LRA=18,aresample=48000'


def pal_video_filter(letterbox):
    if letterbox:
        # Fit the source display aspect (including anamorphic SAR) into a
        # 720x576 PAL 4:3 raster whose samples are 16:15. Keep interlaced
        # height divisible by four so both fields get the same border.
        geometry = ("scale='min(720,round(576*dar*15/32)*2)':'min(576,round(720*16/60/dar)*4)'"
                    ':flags=lanczos:interl=-1,pad=720:576:(ow-iw)/2:(oh-ih)/2:black')
    else:
        geometry = 'scale=720:576:flags=lanczos'
    return geometry + ',setsar=16/15,fps=25,format=yuv420p,setfield=tff'


def pid_of(p):
    return ((p[1] & 0x1f) << 8) | p[2]


class ClientDisconnected(ConnectionError):
    pass


class Weaver:
    """Constant-rate multiplex: the channel's A/V packets pass; every other slot
    (ffmpeg's own PSI, stuffing) carries the next due guide-data packet or a
    null packet. Continuity counters are renumbered for every PID, so the
    joins between ffmpeg runs are seamless to the demux."""
    def __init__(self, si, av_pids):
        self.av = set(av_pids)
        self.slot = 0
        self.cc = {}
        self.set_si(si)

    def set_si(self, si):
        """Start the updated carousel at the current point in the output."""
        self.si_data = si
        self.base = self.slot * P / RATE
        self.si = [(i * P / SI_RATE, si[i * P:(i + 1) * P]) for i in range(len(si) // P)
                   if pid_of(si[i * P:(i + 1) * P]) != 0x1fff]
        self.period = len(si) / SI_RATE
        self.k = 0

    def stamp(self, p):
        pid = pid_of(p)
        c = self.cc.get(pid, 15)
        if p[3] & 0x10:
            c = self.cc[pid] = (c + 1) & 15
        return p[:3] + bytes([(p[3] & 0xf0) | c]) + p[4:]

    def packet(self, p=None):
        now = self.slot * P / RATE
        self.slot += 1
        if p is not None and pid_of(p) in self.av:
            return self.stamp(p)
        if self.si:
            due, sp = self.si[self.k % len(self.si)]
            due += self.base + (self.k // len(self.si)) * self.period
            if due <= now:
                self.k += 1
                return self.stamp(sp)
        return NULL


class Session:
    """One /tune request."""

    def __init__(self, server, chan, on, connection, *, letterbox=False):
        self.srv, self.connection = server, connection
        self.chan, self.on = chan, on
        self.letterbox = letterbox
        self.start = time.time()
        self.sent = 0
        self.item = None
        self.stopped = threading.Event()
        self.si_interval = 5 if self.srv.stations else 60
        self.refresh = time.monotonic() + self.si_interval

    def schedule_time(self):
        """The time on air of the next byte (what the box will show when it plays it)."""
        return self.start + self.sent / RATE

    def send(self, data):
        pending = memoryview(data)
        deadline = time.monotonic() + 25
        while pending:
            if self.stopped.is_set():
                raise ClientDisconnected('playout stopped')
            try:
                count = self.connection.send(pending)
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ClientDisconnected('box stopped reading')
                select.select([], [self.connection], [], 0.2)
                continue
            except OSError as e:
                raise ClientDisconnected(type(e).__name__) from e
            if count == 0:
                raise ClientDisconnected('box closed the connection')
            self.sent += count
            pending = pending[count:]
            deadline = time.monotonic() + 25

    def si(self):
        return self.srv.carousel(self.schedule_time(), self.on)

    def update_si(self, weaver):
        if time.monotonic() >= self.refresh:
            data = self.si()
            if data is not weaver.si_data:
                weaver.set_si(data)
            self.refresh = time.monotonic() + self.si_interval

    def run(self):
        with self.srv.session_lock:
            if self.srv.closing:
                return
            self.srv.sessions.add(self)
        try:
            self.connection.setblocking(False)
            if self.chan == 'music':
                self.music()
            elif self.chan is None:
                self.guide_only()
            elif isinstance(self.chan, RadioStation):
                self.radio()
            elif isinstance(self.chan, LiveChannel):
                self.live()
            else:
                self.channel()
        except ClientDisconnected as e:
            why = f'box disconnected ({e})'
        except Exception:
            import traceback
            why = 'error:\n' + traceback.format_exc()
        else:
            why = 'finished'
        finally:
            self.stopped.set()
            with self.srv.session_lock:
                self.srv.sessions.discard(self)
        self.srv.log(f'session ended after {self.sent / RATE:.0f} s: {why}')

    def stuff(self, weaver, target=None):
        while target is None or self.sent < target:
            packets = CHUNK_PACKETS if target is None else min(CHUNK_PACKETS, (target - self.sent) // P)
            self.send(b''.join(weaver.packet() for _ in range(packets)))
            self.update_si(weaver)

    def guide_only(self):
        self.srv.log('guide data only (no channel tuned)')
        self.stuff(Weaver(self.si(), ()))

    def transcode(self, cmd, weaver, target=None):
        """Read complete packets with a bounded stall timeout and reap FFmpeg on every exit."""
        chunks = queue.Queue(maxsize=4)
        finished = threading.Event()
        with tempfile.TemporaryFile() as errors, subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=errors,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as proc:
            def read():
                try:
                    while not finished.is_set():
                        chunk = proc.stdout.read(P * CHUNK_PACKETS)
                        while not finished.is_set():
                            try:
                                chunks.put(chunk, timeout=0.2)
                                break
                            except queue.Full:
                                continue
                        if not chunk:
                            break
                except OSError:
                    pass

            reader = threading.Thread(target=read, name='ffmpeg output', daemon=True)
            reader.start()
            try:
                deadline = time.monotonic() + 15
                while target is None or self.sent < target:
                    if self.stopped.is_set():
                        raise ClientDisconnected('playout stopped')
                    try:
                        chunk = chunks.get(timeout=0.25)
                    except queue.Empty:
                        if time.monotonic() >= deadline:
                            raise RuntimeError('FFmpeg produced no data for 15 seconds')
                        continue
                    if not chunk:
                        if proc.wait(timeout=2):
                            errors.seek(max(0, errors.seek(0, os.SEEK_END) - 1600))
                            detail = errors.read().decode('utf-8', 'replace').strip()
                            raise RuntimeError(redact(detail or f'FFmpeg exited with code {proc.returncode}'))
                        break
                    size = len(chunk) // P * P
                    if target is not None:
                        size = min(size, target - self.sent)
                    self.send(b''.join(weaver.packet(chunk[i:i + P]) if chunk[i] == 0x47 else weaver.packet()
                                       for i in range(0, size, P)))
                    self.update_si(weaver)
                    deadline = time.monotonic() + 15
            finally:
                finished.set()
                if proc.poll() is None:
                    proc.kill()
                reader.join()

    def music(self):
        """The EPG Background Audio service: the line-up's period MP2, looped, on its PID - a
        continuous broadcast, so it is joined where the wall clock says it has got to."""
        length = self.srv.music_length
        at = self.schedule_time() % length
        self.srv.log(f"EPG background audio: {Path(self.srv.music).name} @{at:.1f}s of {length:.1f}s")
        w = Weaver(self.si(), (MUSIC_PID,))
        cmd = [self.srv.settings['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-nostdin',
               '-ss', f'{at:.3f}', '-stream_loop', '-1', '-i', self.srv.music, '-map', '0:a:0',
               '-af', normalised_audio(GUIDE_LUFS),
               '-c:a', 'mp2', '-ar', '48000', '-ac', '2', '-b:a', f'{AUDIO_KBPS}k',
               '-streamid', f'0:{MUSIC_PID}', '-mpegts_pmt_start_pid', str(MUSIC_PMT),
               '-mpegts_service_id', str(MUSIC_SID), '-muxrate', str(RATE * 8), '-f', 'mpegts', 'pipe:1']
        try:
            self.transcode(cmd, w)
        except (OSError, RuntimeError, subprocess.SubprocessError) as e:
            if isinstance(e, ClientDisconnected):
                raise
            self.srv.log(f'EPG background audio interrupted: {e}')
        self.stuff(w)

    def radio(self):
        station = self.chan
        self.srv.log(f'{station.name}: opening live radio')
        w = Weaver(self.si(), (station.audio_pid,))
        cmd = [self.srv.settings['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-nostdin',
               '-rw_timeout', '6000000', '-probesize', '32768', '-analyzeduration', '1000000',
               '-protocol_whitelist', 'http,https,tcp,tls,crypto',
               '-i', station.url, '-map', '0:a:0', '-af', normalised_audio(TV_LUFS),
               '-c:a', 'mp2', '-ar', '48000', '-ac', '2', '-b:a', f'{AUDIO_KBPS}k',
               '-streamid', f'0:{station.audio_pid}', '-mpegts_pmt_start_pid', str(station.pmt_pid),
               '-mpegts_service_id', str(station.sid), '-muxrate', str(RATE * 8),
               '-f', 'mpegts', 'pipe:1']
        while not self.stopped.is_set():
            try:
                self.transcode(cmd, w)
            except ClientDisconnected:
                raise
            except (OSError, RuntimeError, subprocess.SubprocessError):
                pass
            self.srv.log(f'{station.name}: radio stream ended, reconnecting')
            self.stuff(w, self.sent + RATE // P * P)
            if self.stopped.wait(1):
                return

    def live(self):
        """An IPTV channel: the stream converted like a scheduled channel's programmes, for
        as long as the box stays tuned; a dropped stream is reopened."""
        c = self.chan
        self.srv.log(f'{c.name}: opening live TV')
        self.item = dict(kind='live', title='Live TV', source=c.url)
        w = Weaver(self.si(), (c.video_pid, c.audio_pid))
        cmd = [self.srv.settings['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-nostdin',
               '-rw_timeout', '10000000', '-protocol_whitelist', 'http,https,tcp,tls,crypto']
        if '.m3u8' in c.url:
            # FAST channels (Amagi etc.) splice adverts in as segments with unusual URL endings
            cmd += ['-extension_picky', '0']
        cmd += ['-i', c.url, '-map', '0:v:0', '-map', '0:a:0',
                '-vf', pal_video_filter(self.letterbox), '-af', normalised_audio(TV_LUFS),
                '-c:v', 'mpeg2video', '-flags', '+ilme+ildct', '-g', '12', '-bf', '2',
                '-b:v', f'{VIDEO_KBPS}k', '-maxrate', f'{VIDEO_KBPS + 600}k', '-bufsize', '1835k',
                '-c:a', 'mp2', '-ar', '48000', '-ac', '2', '-b:a', f'{AUDIO_KBPS}k',
                '-streamid', f'0:{c.video_pid}', '-streamid', f'1:{c.audio_pid}',
                '-mpegts_pmt_start_pid', str(c.pmt_pid), '-mpegts_service_id', str(c.sid),
                '-muxrate', str(RATE * 8), '-pcr_period', '20', '-muxdelay', '0.7', '-f', 'mpegts', 'pipe:1']
        while not self.stopped.is_set():
            try:
                self.transcode(cmd, w)
            except ClientDisconnected:
                raise
            except (OSError, RuntimeError, subprocess.SubprocessError):
                pass
            self.srv.log(f'{c.name}: live stream ended, reconnecting')
            self.stuff(w, self.sent + RATE // P * P)
            if self.stopped.wait(1):
                return

    def channel(self):
        c = self.chan
        w = Weaver(self.si(), (c.video_pid, c.audio_pid))
        while True:
            on_air = self.schedule_time()
            it, offset, day = c.at(on_air)
            remaining = min(it['length'] - offset, (day + 1) * 86400 + c.start - on_air)
            target = self.sent + max(1, int(remaining * RATE / P + 0.999999)) * P
            if remaining < 0.5:                 # too short to be worth a run: skip ahead in stuffing
                self.stuff(w, target)
                continue
            self.item = dict(it, offset=offset)
            self.srv.log(f"{c.name}: {it['kind']} '{it['title']}' {Path(it['source']).name} "
                         f"@{it['inpoint'] + offset:.1f}s for {remaining:.1f}s")
            try:
                cmd = self.srv.ffmpeg_cmd(c, it['source'], it['inpoint'] + offset, remaining, letterbox=self.letterbox)
                self.transcode(cmd, w, target)
            except ClientDisconnected:
                raise
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as e:
                self.srv.log(f"{c.name}: {it['title']} unavailable: {e}")
            # hold the schedule: pad (or the next run starts early) to the item's exact end
            self.stuff(w, target)


class Server(ThreadingHTTPServer):
    daemon_threads = False

    def handle_error(self, request, client_address):
        """Request errors go to the log (a windowed app has no stderr)."""
        import traceback
        if isinstance(sys.exc_info()[1], ConnectionError):
            return  # normal disconnect, including sockets closed during a line-up reload
        self.log(f'request from {client_address[0]} failed:\n' + traceback.format_exc())

    def __init__(self, port, lineup, settings, log=None):
        self.settings = settings
        self.log_sink = log            # the GUI's log, when running inside the app
        self.lineup_path = lineup
        self.history = deque(maxlen=40)
        self.session_lock = threading.Lock()
        self.sessions = set()
        self.requests = set()
        self.closing = False
        cfg = read_lineup(lineup)
        self.chans, self.media = load_lineup(lineup, settings, self.log, cfg=cfg)
        self.by_video = {c.video_pid: c for c in self.chans}
        self.stations = load_radio(cfg, self.log)
        self.by_audio = {station.audio_pid: station for station in self.stations}
        music = cfg.get('epg_music')
        self.music = None
        if music:
            m = Path(settings.get('data_root') or '.') / music
            try:
                info = self.media.probe(str(m))
                if not info.get('audio'):
                    raise ValueError('no audio stream')
                self.music_length = info['duration']
                self.music = str(m)
                self.log(f'EPG background audio service on: {m.name}')
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as e:
                self.log(f'EPG audio unavailable; using silent guide transport: {m}: {e}')
        from pace_huffman import FirmwareHuffman
        self.codec = FirmwareHuffman.from_file(settings['huffman_ram'])
        self._si = {}
        self._si_lock = threading.Lock()
        self._radio_titles, self._radio_version = {}, 0
        super().__init__(('0.0.0.0', port), Handler)
        self.radio_metadata = RadioMetadata(self.stations)

    def server_close(self):
        if hasattr(self, 'radio_metadata'):
            self.radio_metadata.stop.set()
        with self.session_lock:
            self.closing = True
            for session in self.sessions:
                session.stopped.set()
            for request in self.requests:
                try:
                    request.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        super().server_close()

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(2)
        return connection, address

    def process_request(self, request, client_address):
        with self.session_lock:
            self.requests.add(request)
        try:
            super().process_request(request, client_address)
        except BaseException:
            with self.session_lock:
                self.requests.discard(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.session_lock:
                self.requests.discard(request)

    def tune(self, video, freq, audio=0x1fff):
        channel = self.by_video.get(video & 0x1fff)
        if channel is None:
            channel = self.by_audio.get(audio & 0x1fff)
        on = transport_of(freq) if freq else CHAN_TSID if channel else HOME_TSID
        if on == HOME_TSID:
            return ('music' if self.music else None), on
        return channel, on

    def log(self, msg):
        line = time.strftime('%H:%M:%S ') + redact(msg)
        if self.log_sink:
            self.log_sink(line)
        else:
            print(line, flush=True)
        self.history.append(line)

    def carousel(self, when, on=HOME_TSID):
        override = os.environ.get('PACE_SI_FILE')       # diagnostics: send a fixed carousel
        if override:
            return Path(override).read_bytes()
        with self._si_lock:
            titles = self.radio_metadata.snapshot()
            if titles != self._radio_titles:
                self._radio_titles = titles
                self._radio_version += 1
                self._si.clear()
            stamp, si = self._si.get(on, (0, None))
            slot_changed = self.stations and int(when) // 1800 != int(stamp) // 1800
            if si is None or slot_changed or abs(when - stamp) > 60 or int(when) // 86400 != int(stamp) // 86400:
                tables, today = lineup_tables(when, self.codec, self.chans, int(self.settings['days']),
                                              music=True, on=on, stations=self.stations, radio_tracks=titles,
                                              radio_version=self._radio_version)
                si = carousel(tables, today)
                self._si[on] = (when, si)
            return si

    def ffmpeg_cmd(self, c, source, start, length, *, letterbox=False):
        info = self.media.probe(source)
        if not info.get('video'):
            raise ValueError('source contains no video stream')
        cmd = [self.settings['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-nostdin',
               '-ss', f'{start:.3f}', '-t', f'{length:.3f}', '-i', info.get('input', source)]
        amap = '0:a:0'
        audio_filter = STEREO_48K
        if info.get('audio'):
            if info.get('audio_index') is not None:
                amap = f"0:{info['audio_index']}"
            audio_filter = normalised_audio(TV_LUFS)
        else:
            cmd += ['-f', 'lavfi', '-t', f'{length:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
            amap = '1:a:0'
        cmd += ['-map', '0:v:0', '-map', amap,
                '-vf', pal_video_filter(letterbox),
                '-af', audio_filter,
                '-c:v', 'mpeg2video', '-flags', '+ilme+ildct', '-g', '12', '-bf', '2',
                '-b:v', f'{VIDEO_KBPS}k', '-maxrate', f'{VIDEO_KBPS + 600}k', '-bufsize', '1835k',
                '-c:a', 'mp2', '-b:a', f'{AUDIO_KBPS}k',
                '-streamid', f'0:{c.video_pid}', '-streamid', f'1:{c.audio_pid}',
                '-mpegts_pmt_start_pid', str(c.pmt_pid), '-mpegts_service_id', str(c.sid),
                '-muxrate', str(RATE * 8), '-pcr_period', '20', '-muxdelay', '0.7', '-f', 'mpegts', 'pipe:1']
        return cmd

    def now(self):
        t = time.time()
        out = []
        for c in self.chans:
            it, off, _ = c.at(t)
            day = datetime.fromtimestamp(t, timezone.utc).date()
            events = c.events_utc(day)
            sod = t % 86400
            cur = next(((s, l, ti) for s, l, ti, _ in events if s <= sod < s + l), None)
            nxt = next(((s, l, ti) for s, l, ti, _ in events if s > sod), None)
            if nxt is None:
                nxt = next(iter(c.events_utc(day + timedelta(days=1))), None)
            out.append(dict(number=c.number, name=c.name, style=c.style,
                            now=cur[2] if cur else '', next=nxt[2] if nxt else '',
                            next_at=f'{nxt[0]//3600:02d}:{nxt[0]//60%60:02d}' if nxt else '',
                            on_air=it['kind'], source=Path(it['source']).name, offset=round(off, 1)))
        with self.session_lock:
            sessions = [dict(channel=('(EPG background audio)' if s.chan == 'music' else s.chan.name if s.chan else '(guide data)'), seconds=round(s.sent / RATE),
                             item=s.item and dict(kind=s.item['kind'], title=s.item['title'],
                                                  source=Path(s.item['source']).name))
                        for s in self.sessions]
        tracks = self.radio_metadata.snapshot()
        radio = [dict(number=s.number, name=s.name, now=tracks.get(s.number, ('', ''))[0]) for s in self.stations]
        return dict(utc=datetime.now(timezone.utc).strftime('%H:%M:%S'), channels=out, radio=radio, streaming=sessions,
                    log=list(self.history.copy())[-15:])


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ('/service', '/tune'):
            q = parse_qs(url.query)
            try:
                video = int(q.get('video', ['0x1fff'])[0], 0)
                audio = int(q.get('audio', ['0x1fff'])[0], 0)
                freq = int(q['freq'][0], 16) if q.get('freq') else None
                letterbox = q.get('letterbox') == ['1']
                if not (0 <= video <= 0xffff and 0 <= audio <= 0xffff and
                        (freq is None or 0 <= freq <= 0xffffffff)):
                    raise ValueError
            except ValueError:
                self.send_error(400, 'Invalid tuning')
                return
            channel, on = self.server.tune(video, freq, audio)
            ident = 'music' if channel == 'music' else str(channel.i) if channel else 'guide'
            if url.path == '/service':
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f'{ident}@{on}'.encode())
                return
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp2t')
            self.send_header('X-Pace-Service', f'{ident}@{on}')
            self.end_headers()
            self.server.log(f'tune from {self.client_address[0]}: video {video:04x} audio {audio:04x}'
                            + (f' at {freq >> 8:x}.{freq & 0xff:02x} MHz' if freq else '')
                            + (' (4:3 letterbox)' if letterbox else ''))
            self.server.last_box = (time.time(), self.client_address[0])
            Session(self.server, channel, on, self.connection, letterbox=letterbox).run()
        elif url.path == '/now.json':
            body = json.dumps(self.server.now(), indent=1).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        elif url.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(STATUS_PAGE.encode())
        else:
            self.send_error(404)


STATUS_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Pace playout</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:15px system-ui,sans-serif;margin:16px;background:#101418;color:#e8e8e8}
table{border-collapse:collapse;width:100%}td,th{padding:6px 8px;border-bottom:1px solid #2a3038;text-align:left}
th{color:#9ab}h1{font-size:20px}.live{color:#6f6}pre{background:#0a0d10;padding:8px;overflow:auto;font-size:12px}</style>
</head><body><h1>Pace 2500N playout <span id=utc></span></h1>
<table><thead><tr><th>No.</th><th>Channel</th><th>Now</th><th>Next</th><th>On air</th></tr></thead><tbody id=ch></tbody></table>
<h2>Streaming to the box</h2><div id=st></div><h2>Log</h2><pre id=log></pre>
<script>
async function tick(){const r=await fetch('/now.json');const d=await r.json();
document.getElementById('utc').textContent=d.utc+' UTC';
const ch=document.getElementById('ch');ch.replaceChildren();
for(const c of d.channels){
  const row=ch.insertRow();
  for(const value of [c.number,`${c.name} (${c.style})`,c.now,`${c.next_at} ${c.next}`,`${c.on_air}: ${c.source} @${c.offset}s`])
    row.insertCell().textContent=value;
}
const st=document.getElementById('st');st.replaceChildren();
for(const s of d.streaming){
  const p=document.createElement('p');p.className='live';
  p.textContent=`● ${s.channel} for ${s.seconds}s ${s.item?'- '+s.item.kind+' '+s.item.title+' ('+s.item.source+')':''}`;
  st.append(p);
}
if(!d.streaming.length)st.textContent='The box has not tuned a channel.';
document.getElementById('log').textContent=d.log.join('\\n');}
tick();setInterval(tick,2000);
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('lineup')
    ap.add_argument('--port', type=int)
    a = ap.parse_args()
    settings = load_settings()
    srv = Server(a.port or int(settings['port']), a.lineup, settings)
    srv.log(f"playout up on port {srv.server_address[1]}: {len(srv.chans)} channel(s) from {a.lineup}")
    srv.serve_forever()


if __name__ == '__main__':
    main()
