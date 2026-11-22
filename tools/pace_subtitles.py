"""Per-tune subtitle extraction. Text/Teletext only; never changes Plex settings.

Workers and queues are bounded. Closing a session kills/reaps its extractor.
Caption time is relative to the same source seek as A/V; the caller uses its
transport output clock, not network/download speed, to select each cue.
"""
import json
import queue
import subprocess
import tempfile
import threading
import time
from collections import deque

from pace_teletext import HAM, Cue, srt_cues, unpack_pes

TEXT = {'subrip', 'srt', 'ass', 'ssa', 'webvtt', 'mov_text', 'text', 'ttml'}
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def preference(track):
    tags = track.get('tags', {})
    lang = str(track.get('languageCode') or track.get('language') or tags.get('language', '')).lower()
    flags = track.get('disposition', {})
    return (lang in ('en', 'eng', 'english'), bool(track.get('selected') or flags.get('default')),
            not bool(track.get('forced') or flags.get('forced')))


def wanted_language(track, media):
    language = str(track.get('languageCode') or track.get('language') or track.get('tags', {}).get('language', '')).lower()
    wanted = str(getattr(media, 's', {}).get('subtitle_language', 'eng')).lower()
    aliases = {'en': {'en', 'eng', 'english'}, 'eng': {'en', 'eng', 'english'}}
    return not language or language in aliases.get(wanted, {wanted})


def select_source(media, source):
    if source.startswith('plex:'):
        part = media.plex_parts(source[5:])[0]
        streams = [s for s in part.get('Stream', []) if int(s.get('streamType', 0)) == 3
                   and s.get('codec', '') in TEXT | {'dvb_teletext'} and wanted_language(s, media)]
        if streams:
            s = max(streams, key=preference)
            if s.get('key', '').startswith('/library/streams/'):
                return media.plex_url(s['key']), '0:0', s.get('codec', ''), s.get('languageCode', ''), 0.
            if s.get('index') is not None:
                return media.plex_url(part['key']), f"0:{int(s['index'])}", s.get('codec', ''), s.get('languageCode', ''), 0.
        # Plex may omit Stream records, but direct ffprobe can still find them.
        url = media.plex_url(part['key'])
    else:
        url = source
    result = subprocess.run([media.ffprobe, '-v', 'error', '-rw_timeout', '10000000',
                             '-show_entries', 'stream=index,codec_type,codec_name,start_time:stream_tags=language:stream_disposition=default,forced',
                             '-of', 'json', url], capture_output=True, timeout=15, creationflags=NO_WINDOW)
    if result.returncode or len(result.stdout) > 2_000_000:
        return None
    all_streams = json.loads(result.stdout).get('streams', [])
    tracks = [s for s in all_streams
              if s.get('codec_type') == 'subtitle' and s.get('codec_name') in TEXT | {'dvb_teletext'} and wanted_language(s, media)]
    if not tracks:
        return None
    s = max(tracks, key=preference)
    video_start = next((float(v.get('start_time') or 0) for v in all_streams if v.get('codec_type') == 'video'), 0.)
    return url, f"0:{int(s['index'])}", s['codec_name'], s.get('tags', {}).get('language', ''), video_start


class PESReader:
    """Bounded TS/PES reader for FFmpeg's copied Teletext output."""
    def __init__(self):
        self.data = {}
        self.cc = {}

    def packet(self, packet):
        if len(packet) != 188 or packet[0] != 0x47:
            return []
        pid = (packet[1] & 31) << 8 | packet[2]
        afc = packet[3] >> 4 & 3
        if packet[1] & 0x80 or packet[3] & 0xc0 or afc == 0:
            self.data.pop(pid, None)
            return []
        pos = 5 + packet[4] if afc & 2 else 4
        if not afc & 1 or pos >= 188:
            return []
        cc = packet[3] & 15
        if pid in self.cc and cc != (self.cc[pid] + 1) & 15:
            self.data.pop(pid, None)
        self.cc[pid] = cc
        result = []
        if packet[1] & 0x40:
            old = self.data.pop(pid, None)
            if old:
                result += unpack_pes(old)
            if packet[pos:pos + 4] == b'\0\0\1\xbd':
                self.data[pid] = bytearray()
        if pid in self.data:
            buf = self.data[pid]
            buf += packet[pos:]
            size = 6 + int.from_bytes(buf[4:6], 'big') if len(buf) >= 6 else 0
            if size > 6 and len(buf) >= size:
                result += unpack_pes(buf[:size])
                self.data.pop(pid, None)
            elif len(buf) > 65536:
                self.data.pop(pid, None)
        return result


class SubtitleRemapper:
    def __init__(self):
        self.selected = None
        self.active = {}

    def packet(self, packet):
        try:
            a, b = HAM.index(packet[3]), HAM.index(packet[4])
        except ValueError:
            return None
        mag, row = a & 7, (a >> 3) | (b << 1)
        if row > 24:
            return None
        packet = bytearray(packet)
        if row == 0:
            try:
                number = (mag, HAM.index(packet[5]), HAM.index(packet[6]))
                flags = HAM.index(packet[10])
            except ValueError:
                self.active[mag] = False
                return None
            if self.selected is None and flags & 8:
                self.selected = number
            self.active[mag] = number == self.selected
            if not self.active[mag]:
                return None
            packet[5] = packet[6] = HAM[8]
            packet[10] = HAM[flags | 8]
            try:
                packet[11] = HAM[HAM.index(packet[11]) | 1]
            except ValueError:
                return None
        if not self.active.get(mag):
            return None
        packet[3] = HAM[(row & 1) << 3]  # magazine8 is encoded as0
        packet[4] = HAM[row >> 1]
        return bytes(packet)


class SubtitleReader:
    def __init__(self, media, source, start=0, length=None, log=lambda _: None):
        self.media, self.source, self.start, self.length, self.log = media, source, start, length, log
        self.stop = threading.Event()
        self.queue = queue.Queue(maxsize=128)
        self.raw = deque(maxlen=256)
        self.kind = 'text'
        self.proc = None
        self.lock = threading.Lock()
        self.pending = None
        self.current = None
        self.thread = threading.Thread(target=self._run, name='Teletext subtitles', daemon=True)
        self.thread.start()

    def _run(self):
        try:
            choice = select_source(self.media, self.source)
            if not choice or self.stop.is_set():
                return
            url, stream, codec, language, video_start = choice
            self.log(f'Teletext 888: {codec} subtitle track ({language or "language unspecified"})')
            self.kind = 'teletext' if codec == 'dvb_teletext' else 'text'
            if codec == 'webvtt' and not self.source.startswith('plex:') and url.startswith(('http:', 'https:')):
                from pace_hls_subtitles import read_hls, NotHLS
                while not self.stop.is_set():
                    try:
                        read_hls(url, video_start, self.stop, self.publish)
                        return
                    except NotHLS:
                        break  # ordinary standalone WebVTT: FFmpeg below
                    except (OSError, ValueError):
                        self.log('Teletext HLS subtitle feed unavailable; retrying independently of A/V')
                        if self.stop.wait(5): return
            cmd = [self.media.ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-rw_timeout', '10000000']
            if self.start:
                cmd += ['-ss', str(self.start)]
            if self.kind == 'teletext':
                cmd += ['-re']
            cmd += ['-i', url, '-map', stream, '-vn', '-an']
            if self.length is not None:
                cmd += ['-t', str(self.length)]
            cmd += (['-c:s', 'copy', '-flush_packets', '1', '-f', 'mpegts'] if self.kind == 'teletext'
                    else ['-c:s', 'srt', '-flush_packets', '1', '-f', 'srt'])
            cmd += ['pipe:1']
            with tempfile.TemporaryFile() as errors:
                with self.lock:
                    if self.stop.is_set():
                        return
                    self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors, creationflags=NO_WINDOW)
                    proc = self.proc
                try:
                    if self.kind == 'teletext':
                        demux, remap = PESReader(), SubtitleRemapper()
                        while not self.stop.is_set():
                            packet = proc.stdout.read(188)
                            if len(packet) != 188:
                                break
                            for raw in demux.packet(packet):
                                raw = remap.packet(raw)
                                if raw:
                                    # Backpressure the extractor, never playout.
                                    while len(self.raw) >= 240 and not self.stop.wait(.02):
                                        pass
                                    if not self.stop.is_set():
                                        self.raw.append(raw)
                    else:
                        lines = (line.decode('utf-8', 'replace') for line in iter(proc.stdout.readline, b''))
                        for cue in srt_cues(lines):
                            self.publish(cue)
                            if self.stop.is_set():
                                break
                finally:
                    if proc.poll() is None:
                        proc.kill()
                    proc.wait(timeout=5)
                    proc.stdout.close()
                    if proc.returncode and not self.stop.is_set():
                        self.log(f'Teletext subtitle extractor stopped (code {proc.returncode}); A/V continues')
        except Exception as exc:
            # Never log a URL or raw FFmpeg stderr containing Plex/IPTV tokens.
            self.log(f'Teletext subtitles unavailable ({type(exc).__name__}); A/V continues')

    def publish(self, cue):
        while not self.stop.is_set():
            try:
                self.queue.put(cue, timeout=.2)
                return
            except queue.Full:
                continue

    def text(self, when):
        if self.kind == 'teletext':
            return None
        while True:
            if self.pending is None:
                try:
                    self.pending = self.queue.get_nowait()
                except queue.Empty:
                    break
            if self.pending.start > when:
                break
            self.current, self.pending = self.pending, None
        return self.current.text if self.current and self.current.start <= when < self.current.end else ''

    def close(self):
        self.stop.set()
        with self.lock:
            if self.proc and self.proc.poll() is None:
                self.proc.kill()
        # A bounded metadata/probe request may still be finishing. It checks
        # stop before launching FFmpeg; retuning must not wait for that request.
        self.thread.join(timeout=.2)
