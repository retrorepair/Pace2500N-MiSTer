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
woven in. Otherwise (the Guide, no channel) it sends the guide data alone.

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
import argparse, json, os, subprocess, sys, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pace_channels import RATE, load_settings, load_lineup, lineup_tables, carousel, MUSIC_PID, MUSIC_PMT, MUSIC_SID  # noqa: E402

P = 188
NULL = bytes([0x47, 0x1f, 0xff, 0x10]) + b'\xff' * 184
VIDEO_KBPS, AUDIO_KBPS = 4300, 192
SI_RATE = 125000                # carousel byte rate (1 Mbit/s)


def pid_of(p):
    return ((p[1] & 0x1f) << 8) | p[2]


class Weaver:
    """Constant-rate multiplex: the channel's A/V packets pass; every other slot
    (ffmpeg's own PSI, stuffing) carries the next due guide-data packet or a
    null packet. Continuity counters are renumbered for every PID, so the
    joins between ffmpeg runs are seamless to the demux."""
    def __init__(self, si, av_pids):
        self.av = set(av_pids)
        self.si = [(i * P / SI_RATE, si[i * P:(i + 1) * P]) for i in range(len(si) // P)
                   if pid_of(si[i * P:(i + 1) * P]) != 0x1fff]
        self.period = len(si) / SI_RATE
        self.k = 0
        self.slot = 0
        self.cc = {}

    def set_si(self, si):
        """New carousel (fresh listings), continuing the same timing."""
        base = (self.k // len(self.si)) * self.period if self.si else 0
        self.si = [(i * P / SI_RATE, si[i * P:(i + 1) * P]) for i in range(len(si) // P)
                   if pid_of(si[i * P:(i + 1) * P]) != 0x1fff]
        self.period = len(si) / SI_RATE
        self.k = int(base / self.period) * len(self.si)

    def stamp(self, p):
        pid = pid_of(p)
        c = self.cc.get(pid, 0)
        self.cc[pid] = (c + 1) & 15
        return p[:3] + bytes([(p[3] & 0xf0) | c]) + p[4:]

    def packet(self, p=None):
        now = self.slot * P / RATE
        self.slot += 1
        if p is not None and pid_of(p) in self.av:
            return self.stamp(p)
        if self.si:
            due, sp = self.si[self.k % len(self.si)]
            due += (self.k // len(self.si)) * self.period
            if due <= now:
                self.k += 1
                return self.stamp(sp)
        return NULL


class Session:
    """One /tune request."""
    active = {}
    lock = threading.Lock()

    def __init__(self, server, video, audio, wfile):
        self.srv, self.wfile = server, wfile
        self.chan = server.service(video, audio)
        self.start = time.time()
        self.sent = 0
        self.item = None
        self.proc = None
        self.stopped = False
        self.audio = audio

    def schedule_time(self):
        """The time on air of the next byte (what the box will show when it plays it)."""
        return self.start + self.sent / RATE

    def send(self, data):
        self.wfile.write(data)
        self.sent += len(data)

    def si(self):
        return self.srv.carousel(self.schedule_time())

    def run(self):
        with Session.lock:
            Session.active[id(self)] = self
        try:
            if self.chan == 'music':
                self.music()
            elif self.chan is None:
                self.guide_only()
            else:
                self.channel()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
            why = f'box disconnected ({type(e).__name__})'
        except Exception:
            import traceback
            why = 'error:\n' + traceback.format_exc()
        else:
            why = 'finished'
        finally:
            self.stopped = True
            if self.proc and self.proc.poll() is None:
                self.proc.kill()
            with Session.lock:
                Session.active.pop(id(self), None)
        self.srv.log(f'session ended after {self.sent / RATE:.0f} s: {why}')

    def guide_only(self):
        self.srv.log('guide data only (no channel tuned)')
        w = Weaver(self.si(), ())
        refresh = time.time() + 60
        while True:
            self.send(b''.join(w.packet() for _ in range(348)))   # 64 KiB
            if time.time() > refresh:
                w.set_si(self.si()); refresh = time.time() + 60

    def music(self):
        """The EPG Background Audio service: the line-up's period MP2, looped, on its PID."""
        self.srv.log(f"EPG background audio: {Path(self.srv.music).name}")
        w = Weaver(self.si(), (MUSIC_PID,))
        refresh = time.time() + 60
        cmd = [self.srv.settings['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-nostdin',
               '-stream_loop', '-1', '-i', self.srv.music, '-map', '0:a:0', '-c:a', 'copy',
               '-streamid', f'0:{MUSIC_PID}', '-mpegts_pmt_start_pid', str(MUSIC_PMT),
               '-mpegts_service_id', str(MUSIC_SID), '-muxrate', str(RATE * 8), '-f', 'mpegts', 'pipe:1']
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        buf = b''
        while True:
            chunk = self.proc.stdout.read(P * 348)
            if not chunk:
                break
            buf += chunk
            n = len(buf) // P * P
            self.send(b''.join(w.packet(buf[i:i + P]) for i in range(0, n, P) if buf[i] == 0x47))
            buf = buf[n:]
            if time.time() > refresh:
                w.set_si(self.si()); refresh = time.time() + 60

    def channel(self):
        c = self.chan
        w = Weaver(self.si(), (c.video_pid, c.audio_pid))
        refresh = time.time() + 60
        while True:
            it, offset, _ = c.at(self.schedule_time())
            remaining = it['length'] - offset
            if remaining < 0.5:                 # too short to be worth a run: skip ahead in stuffing
                for _ in range(int(remaining * RATE / P) + 1):
                    self.send(w.packet())
                continue
            self.item = dict(it, offset=offset)
            self.srv.log(f"{c.name}: {it['kind']} '{it['title']}' {Path(it['source']).name} "
                         f"@{it['inpoint'] + offset:.1f}s for {remaining:.1f}s")
            self.proc = subprocess.Popen(self.srv.ffmpeg_cmd(c, it['source'], it['inpoint'] + offset, remaining),
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            target = self.sent + int(remaining * RATE)
            buf = b''
            while True:
                chunk = self.proc.stdout.read(P * 348)
                if not chunk:
                    break
                buf += chunk
                n = len(buf) // P * P
                out = b''.join(w.packet(buf[i:i + P]) for i in range(0, n, P) if buf[i] == 0x47)
                buf = buf[n:]
                self.send(out)
                if time.time() > refresh:
                    w.set_si(self.si()); refresh = time.time() + 60
            self.proc.wait()
            # hold the schedule: pad (or the next run starts early) to the item's exact end
            while self.sent < target:
                self.send(w.packet())


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        """Request errors go to the log (a windowed app has no stderr)."""
        import traceback
        self.log(f'request from {client_address[0]} failed:\n' + traceback.format_exc())

    def __init__(self, port, lineup, settings, log=None):
        self.settings = settings
        self.log_sink = log            # the GUI's log, when running inside the app
        self.lineup_path = lineup
        self.history = []
        self.chans, self.media = load_lineup(lineup, settings, self.log)
        music = json.loads(Path(lineup).read_text()).get('epg_music')
        self.music = None
        if music:
            m = Path(music) if Path(music).is_absolute() else Path(settings.get('data_root', '.')) / music
            if m.exists():
                self.music = str(m)
                self.log(f'EPG background audio service on: {m.name}')
            else:
                self.log(f'epg_music not found: {m}')
        from pace_huffman import FirmwareHuffman
        self.codec = FirmwareHuffman.from_file(settings['huffman_ram'])
        self._si = (0, None)
        self._si_lock = threading.Lock()
        super().__init__(('0.0.0.0', port), Handler)

    def service(self, video, audio):
        """The channel the firmware has tuned: by its video PID, or -- in the Guide,
        where the firmware stops video but the channel's sound carries on -- by
        its audio PID. None = no channel (guide data only)."""
        v, a = video & 0x1fff, audio & 0x1fff
        if self.music and v == 0x1fff and a == MUSIC_PID:
            return 'music'
        return (next((c for c in self.chans if c.video_pid == v), None)
                or next((c for c in self.chans if c.audio_pid == a), None))

    def log(self, msg):
        line = time.strftime('%H:%M:%S ') + msg
        if self.log_sink:
            self.log_sink(line)
        else:
            print(line, flush=True)
        self.history = (self.history + [line])[-40:]

    def carousel(self, when):
        override = os.environ.get('PACE_SI_FILE')       # diagnostics: send a fixed carousel
        if override:
            return Path(override).read_bytes()
        with self._si_lock:
            stamp, si = self._si
            if si is None or abs(when - stamp) > 60:
                tables, today = lineup_tables(when, self.codec, self.chans, int(self.settings['days']),
                                              music=bool(self.music))
                si = carousel(tables, today)
                self._si = (when, si)
            return si

    def ffmpeg_cmd(self, c, source, start, length):
        info = self.media.probe(source)
        cmd = [self.settings['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-nostdin',
               '-ss', f'{start:.3f}', '-t', f'{length:.3f}', '-i', self.media.url(source)]
        amap = '0:a:0'
        if not info.get('audio'):
            cmd += ['-f', 'lavfi', '-t', f'{length:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
            amap = '1:a:0'
        cmd += ['-map', '0:v:0', '-map', amap,
                '-vf', 'scale=720:576:flags=lanczos,setsar=16/15,fps=25,format=yuv420p,setfield=tff',
                '-af', 'aresample=48000,aformat=channel_layouts=stereo',
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
            events = c.events_utc(datetime.now(timezone.utc).date())
            sod = t % 86400
            cur = next(((s, l, ti) for s, l, ti in events if s <= sod < s + l), None)
            nxt = next(((s, l, ti) for s, l, ti in events if s > sod), None)
            out.append(dict(number=c.number, name=c.name, style=c.style,
                            now=cur[2] if cur else '', next=nxt[2] if nxt else '',
                            next_at=f'{nxt[0]//3600:02d}:{nxt[0]//60%60:02d}' if nxt else '',
                            on_air=it['kind'], source=Path(it['source']).name, offset=round(off, 1)))
        with Session.lock:
            sessions = [dict(channel=('(EPG background audio)' if s.chan == 'music' else s.chan.name if s.chan else '(guide data)'), seconds=round(s.sent / RATE),
                             item=s.item and dict(kind=s.item['kind'], title=s.item['title'],
                                                  source=Path(s.item['source']).name))
                        for s in Session.active.values()]
        return dict(utc=datetime.now(timezone.utc).strftime('%H:%M:%S'), channels=out, streaming=sessions,
                    log=self.history[-15:])


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/tune':
            q = parse_qs(url.query)
            video = int(q.get('video', ['0x1fff'])[0], 0)
            audio = int(q.get('audio', ['0x1fff'])[0], 0)
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp2t')
            self.end_headers()
            self.server.log(f'tune from {self.client_address[0]}: video {video:04x} audio {audio:04x}')
            self.server.last_box = (time.time(), self.client_address[0])
            Session(self.server, video, audio, self.wfile).run()
        elif url.path == '/service':
            # which service a tuning means (the relay keeps its stream when unchanged)
            q = parse_qs(url.query)
            c = self.server.service(int(q.get('video', ['0x1fff'])[0], 0), int(q.get('audio', ['0x1fff'])[0], 0))
            body = ('music' if c == 'music' else str(c.i) if c else 'guide').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(body)
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
document.getElementById('ch').innerHTML=d.channels.map(c=>`<tr><td>${c.number}</td><td>${c.name} <small>(${c.style})</small></td><td>${c.now}</td><td>${c.next_at} ${c.next}</td><td>${c.on_air}: ${c.source} @${c.offset}s</td></tr>`).join('');
document.getElementById('st').innerHTML=d.streaming.length?d.streaming.map(s=>`<p class=live>&#9679; ${s.channel} for ${s.seconds}s ${s.item?'- '+s.item.kind+' '+s.item.title+' ('+s.item.source+')':''}</p>`).join(''):'<p>Nothing - the box has not tuned a channel.</p>';
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
