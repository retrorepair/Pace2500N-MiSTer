#!/usr/bin/env python3
"""Pace 2500N channels: line-up metadata, media library, schedule and guide data.

A line-up is pure metadata (JSON). Nothing here makes video files: the
playout server (tools/pace_playout.py) transcodes on demand from the sources
the line-up points at, only while the box is tuned to that channel.

Line-up file (see tools/lineup.example.json):
  {
    "channels": [
      {"name": "BBC1", "number": 101, "style": "bbc", "start": "06:00",
       "interstitials": ["roms/interstitials/bbc1_1988_89"],
       "programmes": [{"title": "Children's BBC", "source": "X:/Old Kids TV/....mpg",
                       "inpoint": 0, "duration": null}]}
    ]
  }
  style   bbc  : no adverts; continuity (announcers, trailers, idents) between programmes
          itv  : terrestrial commercial: centre breaks + end breaks of period adverts/idents
          sky  : satellite commercial: as itv, Sky-length breaks
  start   the broadcast day begins here (UTC); the programme list repeats to fill 24 h
  source  a file path, or plex:<ratingKey> (a Plex library item; needs the Plex settings)

Interstitial sets are folders of period recordings (YouTube rips of advert
breaks / continuity, kept under roms/). `split` finds the cuts between spots
(black frames that coincide with silence) and records them; breaks are then
filled with contiguous runs of spots exactly as they were recorded off air.

Service numbering: channel i (0-based) is SID 1001+i, PMT PID 0x1000+i,
video PID 0x200+0x10*i, audio PID 0x102+0x10*i, OpenTV listing 3000+i.
"""
import argparse, hashlib, json, os, random, re, subprocess, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent              # data folder (line-ups, roms/); the app sets it from settings
FROZEN = getattr(sys, 'frozen', False)          # running as the packaged Windows app
APP_DIR = Path(sys.executable).parent if FROZEN else None
# no console window flashing up for every ffmpeg/ffprobe run from the GUI
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
sys.path.insert(0, str(HERE))
from pace_si import u16, loop, descriptor, long_section, tot, title_section  # noqa: E402
from pace_transport import Packetizer  # noqa: E402

RATE = 781250                    # stream bytes per second (6.25 Mbit/s, the core's replay rate)
EPOCH = date(1858, 11, 17)


def bundled(name):
    """A tool shipped next to the packaged app (ffmpeg.exe, ffprobe.exe, yt-dlp.exe)."""
    if APP_DIR and (APP_DIR / 'tools' / name).exists():
        return str(APP_DIR / 'tools' / name)
    return None


def default_ffmpeg():
    if bundled('ffmpeg.exe'):
        return bundled('ffmpeg.exe')
    local = sorted(ROOT.glob('third_party/ffmpeg-*/bin/ffmpeg.exe'))
    return str(local[-1]) if local else 'ffmpeg'


def settings_path():
    base = os.environ.get('APPDATA') or str(Path.home() / '.config')
    return Path(base) / 'Pace2500N' / 'settings.json'


def load_settings():
    p = settings_path()
    s = json.loads(p.read_text()) if p.exists() else {}
    global ROOT
    if s.get('data_root') and Path(s['data_root']).is_dir():
        ROOT = Path(s['data_root'])
    if FROZEN and bundled('ffmpeg.exe') and not Path(s.get('ffmpeg', '')).exists():
        s['ffmpeg'] = bundled('ffmpeg.exe')
    s.setdefault('ffmpeg', default_ffmpeg())
    s.setdefault('port', 8250)
    s.setdefault('huffman_ram', str(ROOT / 're' / 'fpga_guide_checkpoint' / 'RAM.bin'))
    s.setdefault('library_cache', str(ROOT / 'roms' / 'library_cache.json'))
    s.setdefault('days', 7)
    return s


def save_settings(s):
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s, indent=2))


def hms(text):
    parts = [int(x) for x in str(text).split(':')]
    while len(parts) < 3:
        parts.append(0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


# ------------------------------------------------------------------ media access
class Media:
    """ffprobe/ffmpeg analysis with a persistent cache, and Plex resolution."""
    def __init__(self, settings):
        self.s = settings
        self.ffmpeg = settings['ffmpeg']
        self.ffprobe = re.sub(r'ffmpeg(\.exe)?$', lambda m: 'ffprobe' + (m.group(1) or ''), self.ffmpeg)
        self.cache_path = Path(settings['library_cache'])
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}
        self._keys = {}

    def save(self):
        """Merge into the file per entry: other tools (the builder, a prepare run)
        may have added analysis since this process loaded it."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            disk = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}
        except ValueError:
            disk = {}
        for k, v in self.cache.items():
            disk[k] = {**disk.get(k, {}), **v}
        self.cache = disk
        tmp = self.cache_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(disk, indent=1))
        os.replace(tmp, self.cache_path)

    def url(self, source):
        """Something ffmpeg can open."""
        if source.startswith('plex:'):
            return self.plex_part(source[5:])
        return source

    def key(self, source):
        if source.startswith('plex:'):
            return source
        k = self._keys.get(source)
        if k is None:      # stat once per run: sources are often on a network share
            st = os.stat(source)
            k = self._keys[source] = f'{Path(source).resolve()}|{st.st_size}|{int(st.st_mtime)}'
        return k

    def plex_part(self, rating_key):
        import urllib.request
        base, token = self.s.get('plex_url'), self.s.get('plex_token')
        if not base or not token:
            raise RuntimeError('Plex source used but plex_url/plex_token are not set')
        req = urllib.request.Request(f'{base}/library/metadata/{rating_key}?X-Plex-Token={token}',
                                     headers={'Accept': 'application/json'})
        meta = json.load(urllib.request.urlopen(req, timeout=10))
        part = meta['MediaContainer']['Metadata'][0]['Media'][0]['Part'][0]['key']
        return f'{base}{part}?X-Plex-Token={token}'

    def probe(self, source):
        k = self.key(source)
        hit = self.cache.get(k, {})
        if 'duration' not in hit:
            out = subprocess.run(creationflags=NO_WINDOW, args=[self.ffprobe, '-v', 'error', '-show_entries',
                                  'format=duration:stream=codec_type,codec_name,width,height',
                                  '-of', 'json', self.url(source)], capture_output=True, text=True)
            if out.returncode:
                raise RuntimeError(f'ffprobe failed for {source}: {out.stderr.strip()}')
            info = json.loads(out.stdout)
            hit.update(duration=float(info['format']['duration']),
                       audio=any(s['codec_type'] == 'audio' for s in info['streams']),
                       video=next(({k: s.get(k) for k in ('codec_name', 'width', 'height')}
                                   for s in info['streams'] if s['codec_type'] == 'video'), None))
            self.cache[k] = hit
            self.save()
        return hit

    def cuts(self, source, log=print):
        """Spot boundaries: midpoints of black frames that coincide with silence."""
        k = self.key(source)
        hit = self.cache.setdefault(k, {})
        if 'cuts' not in hit or 'silence' not in hit:
            log(f'analysing cuts: {source}')
            out = subprocess.run(creationflags=NO_WINDOW, args=[self.ffmpeg, '-hide_banner', '-nostdin', '-i', self.url(source),
                                  '-vf', 'scale=128:-2,blackdetect=d=0.06:pix_th=0.12:pic_th=0.95',
                                  '-af', 'silencedetect=n=-42dB:d=0.12', '-f', 'null', '-'],
                                 capture_output=True, text=True, errors='replace')
            black = [(float(a), float(b)) for a, b in
                     re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', out.stderr)]
            silence_start = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', out.stderr)]
            silence_end = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', out.stderr)]
            silence = list(zip(silence_start, silence_end))
            cuts = []
            for a, b in black:
                if any(sa < b + 0.2 and se > a - 0.2 for sa, se in silence):
                    cuts.append(round((a + b) / 2, 3))
            hit['cuts'] = cuts
            hit['black'] = [round((a + b) / 2, 3) for a, b in black]
            hit['silence'] = [[round(a, 3), round(b, 3)] for a, b in silence]
            self.save()
        return hit['cuts']


VIDEO_SUFFIXES = ('.mkv', '.mp4', '.webm', '.mpg', '.mpeg', '.ts', '.avi', '.m4v', '.mov')


def set_folder(folder):
    """Relative sets are under the data folder (the same for every tool)."""
    return Path(folder) if Path(folder).is_absolute() else ROOT / folder


def recording_spots(media, f, log=print):
    """Every segment of one recording between detected cuts: [(start, length)].
    A long compilation (one YouTube video of a whole evening's breaks) becomes its
    individual adverts / idents / continuity items."""
    dur = media.probe(str(f))['duration']
    cuts = media.cuts(str(f), log)
    hit = media.cache[media.key(str(f))]
    if len(hit['silence']) < dur / 60:
        # tape hiss above the silence threshold: black frames alone mark the cuts
        cuts = hit['black']
    cuts = [c for c in cuts if 1.0 < c < dur - 1.0]
    edges = [0.0] + cuts + [dur]
    # Continuity often cuts straight between items (no black frame): split
    # long stretches at the announcer's pauses instead (silence >= 0.3 s).
    pauses = [(a + b) / 2 for a, b in hit['silence'] if b - a >= 0.3]
    fine = []
    for a, b in zip(edges, edges[1:]):
        fine.append(a)
        if b - a > 150:
            last = a
            for q in pauses:
                if last + 25 <= q <= b - 10:
                    fine.append(q)
                    last = q
    edges = sorted(set(fine + [dur]))
    return [(a, b - a) for a, b in zip(edges, edges[1:])]


def spot_id(f, start):
    return f'{Path(f).name}@{start:.1f}'


def excluded_spots(folder):
    p = set_folder(folder) / 'excluded.json'
    return set(json.loads(p.read_text())) if p.exists() else set()


def set_excluded(folder, ids):
    (set_folder(folder) / 'excluded.json').write_text(json.dumps(sorted(ids), indent=1))


def usable(length):
    return 2.0 <= length <= 240.0


def interstitial_runs(media, folders, log=print):
    """Usable spots of every recording in the sets: lists of (source, start, length)
    that were broadcast back to back. A run is broken wherever a segment is
    unusable (too short/long, e.g. a programme excerpt) or excluded by the user,
    so a break never jumps over it."""
    runs = []
    for folder in folders:
        folder = set_folder(folder)
        excluded = excluded_spots(folder)
        for f in sorted(folder.glob('*')):
            # yt-dlp's per-stream parts (NAME.f251.webm) and unfinished downloads are not recordings
            if f.suffix.lower() not in VIDEO_SUFFIXES or re.search(r'\.f\d+$', f.stem):
                continue
            try:
                spots = recording_spots(media, f, log)
            except Exception as e:      # one unreadable file must not take every channel off air
                log(f'skipping {f.name} in {folder.name}: {e}')
                continue
            run = []
            for a, ln in spots:
                if usable(ln) and spot_id(f, a) not in excluded:
                    run.append((str(f), a, ln))
                elif run:
                    runs.append(run)
                    run = []
            if run:
                runs.append(run)
    return runs


# ------------------------------------------------------------------ schedule
STYLE = {
    # centre-break spacing (s of programme), centre break length, end break length, between
    'itv': dict(every=1320, centre=(150, 210), end=(120, 200)),
    'sky': dict(every=1200, centre=(180, 240), end=(150, 240)),
    'bbc': dict(every=None, centre=None, end=(40, 150)),
}


class Channel:
    def __init__(self, index, cfg, media, log=print):
        self.i = index
        self.name = cfg['name']
        self.number = int(cfg.get('number', 101 + index))
        self.style = cfg.get('style', 'bbc')
        self.start = hms(cfg.get('start', '06:00'))
        self.sid, self.listing = 1001 + index, 3000 + index
        self.pmt_pid, self.video_pid, self.audio_pid = 0x1000 + index, 0x200 + 0x10 * index, 0x102 + 0x10 * index
        self.media = media
        self.programmes = []
        for p in cfg['programmes']:
            inpoint = float(p.get('inpoint') or 0)
            dur = float(p.get('duration') or (media.probe(p['source'])['duration'] - inpoint))
            self.programmes.append(dict(title=p['title'], source=p['source'], inpoint=inpoint, duration=dur,
                                        breaks=p.get('breaks', 'auto')))
        self.runs = interstitial_runs(media, cfg.get('interstitials', []), log)
        self._days = {}

    def _break(self, rng, lo, hi):
        """A contiguous run of off-air spots of about lo..hi seconds."""
        if not self.runs:
            return []
        for _ in range(20):
            run = rng.choice(self.runs)
            j = rng.randrange(len(run))
            out, total = [], 0.0
            while j < len(run) and total < lo:
                out.append(run[j]); total += run[j][2]; j += 1
            if lo <= total <= hi + 60:
                return out
        return out

    def _split_points(self, p, n):
        """n centre-break positions in programme p: evenly spaced, moved to the
        nearest black frame within 90 s when the recording has one."""
        want = [p['duration'] * (k + 1) / (n + 1) for k in range(n)]
        black = []
        if p['breaks'] == 'auto' and not p['source'].startswith('plex:'):
            # only analysed recordings (pace_channels.py prepare): playout never blocks on it
            hit = self.media.cache.get(self.media.key(p['source']), {})
            black = [b - p['inpoint'] for b in hit.get('black', [])]
        pts = []
        for w in want:
            near = [b for b in black if abs(b - w) <= 90 and 60 < b < p['duration'] - 60]
            pts.append(min(near, key=lambda b: abs(b - w)) if near else w)
        return sorted(set(round(x, 2) for x in pts))

    def day(self, n):
        """Broadcast day n (days since 1970-01-01 at `start` UTC): items and guide events,
        times in seconds from the start of that broadcast day. Deterministic."""
        if n in self._days:
            return self._days[n]
        rng = random.Random(f'{self.name}|{n}')
        style = STYLE[self.style]
        items, events = [], []
        t = 0.0
        k = n % max(1, len(self.programmes))
        while t < 86400:
            p = self.programmes[k % len(self.programmes)]
            k += 1
            slot = t
            nbreaks = int(p['duration'] // style['every']) if style['every'] else 0
            points = self._split_points(p, nbreaks) if nbreaks else []
            edges = [0.0] + points + [p['duration']]
            for j, (a, b) in enumerate(zip(edges, edges[1:])):
                items.append(dict(kind='programme', title=p['title'], source=p['source'],
                                  inpoint=p['inpoint'] + a, start=t, length=b - a))
                t += b - a
                if j < len(edges) - 2:
                    for src, s0, ln in self._break(rng, *style['centre']):
                        items.append(dict(kind='break', title=p['title'], source=src, inpoint=s0, start=t, length=ln))
                        t += ln
            for src, s0, ln in self._break(rng, *style['end']):
                items.append(dict(kind='continuity' if self.style == 'bbc' else 'break', title='',
                                  source=src, inpoint=s0, start=t, length=ln))
                t += ln
            events.append((slot, t - slot, p['title']))
        self._days[n] = (items, events)
        return items, events

    def at(self, utc_seconds):
        """(item, offset into it) on air at an absolute UTC time (seconds since 1970)."""
        rel = utc_seconds - self.start
        n, pos = int(rel // 86400), rel % 86400
        items, _ = self.day(n)
        for it in items:
            if it['start'] <= pos < it['start'] + it['length']:
                return it, pos - it['start'], n
        return items[-1], 0.0, n

    def events_utc(self, d):
        """Guide events for UTC calendar day d: (start, length, title), even seconds, clipped."""
        midnight = datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()
        out = []
        for n in (int((midnight - self.start) // 86400) + x for x in (0, 1)):
            base = n * 86400 + self.start
            for s, ln, title in self.day(n)[1]:
                # the next broadcast day takes over at its start
                a, b = base + s - midnight, min(base + s + ln, base + 86400) - midnight
                a, b = max(a, 0), min(b, 86400)
                a, b = int(a) // 2 * 2, int(b) // 2 * 2
                if b > a and not (out and out[-1][0] == a):
                    out.append((a, b - a, title))
        return out


def load_lineup(path, settings, log=print):
    cfg = json.loads(Path(path).read_text())
    media = Media(settings)
    chans = []
    for i, c in enumerate(cfg['channels']):
        if not c.get('programmes'):
            # nothing to schedule: leave it off air rather than fail every channel's guide
            log(f"{c.get('name', 'channel')}: no programmes yet - not broadcast")
            continue
        chans.append(Channel(i, c, media, log))
    return chans, media


# ------------------------------------------------------------------ guide data (SI)
# The EPG Background Audio service (experiment, line-up key "epg_music"): an audio-only
# radio service as Sky broadcast on the EPG transponder (SID 4152, audio PID 0x288 per a
# 2013-15 channels.conf; unverified for 2002), with its own 0xB1 entry so the box makes a
# service record for it, and the Guide's 0x91 home-service linkage pointing at it. Whether
# the firmware plays it in the Guide is what the experiment measures (CURRENT_STATUS.md).
MUSIC_SID, MUSIC_PMT, MUSIC_PID, MUSIC_LISTING = 4152, 0x10ff, 0x288, 0x0fff


def lineup_tables(now, codec, chans, days, music=False):
    when = datetime.fromtimestamp(int(now), timezone.utc)
    # The service tables' version_number follows the channel set, as a broadcaster's does:
    # a box keeps the service list it has (the Guide checkpoint holds one) until the version
    # changes. 1-31, so a line-up never matches the version-0 tables the checkpoint was made with.
    shape = repr([(c.sid, c.number, c.listing, c.name, c.pmt_pid, c.video_pid, c.audio_pid) for c in chans]
                 + ([MUSIC_SID] if music else []))
    ver = 1 + int(hashlib.md5(shape.encode()).hexdigest(), 16) % 31
    namespace = bytes.fromhex('5f0400000002')
    service_list = descriptor(0x41, b''.join(u16(c.sid) + b'\x01' for c in chans)
                              + (u16(MUSIC_SID) + b'\x02' if music else b''))
    satellite = descriptor(0x43, bytes.fromhex('011778000282a102750002'))   # 11778 V, 28.2E
    transport = u16(0) + u16(0x20)
    nit = long_section(0x40, 0x20, loop(descriptor(0x40, b'PACE PLAYOUT'))
                       + loop(transport + loop(satellite + service_list)), version=ver)
    sdt_body = u16(0x20) + b'\xff'
    for c in chans:
        name = c.name.encode('latin-1', 'replace')[:40]
        desc = namespace + descriptor(0x48, b'\x01\x05PLAYO' + bytes((len(name),)) + name)
        it, _, _ = c.at(now)
        current = it['title'] or next((t for s, l, t in c.events_utc(when.date())
                                       if s <= now % 86400 < s + l), c.name)
        desc += descriptor(0xb2, bytes((1, 0, 3 << 5)) + codec.encode(current))
        sdt_body += u16(c.sid) + b'\xfc' + u16(0x8000 | len(desc)) + desc
    if music:
        name = b'EPG Background Audio'
        desc = namespace + descriptor(0x48, b'\x02\x05BSkyB' + bytes((len(name),)) + name)
        sdt_body += u16(MUSIC_SID) + b'\xfc' + u16(0x8000 | len(desc)) + desc
    sdt = long_section(0x42, 0, sdt_body, version=ver)
    linkage = descriptor(0x4a, transport + u16(MUSIC_SID if music else chans[0].sid) + b'\x91')
    # B1 entries: service id, type, channel id, channel number (shown by the
    # guide), then the field carrying the guide-visible flags 6
    lineup = b'\xff\xff' + b''.join(u16(c.sid) + b'\x01' + u16(c.listing) + u16(c.number)
                                      + u16(c.number << 4 | 6) for c in chans)
    if music:      # a record for the box, with no channel number (not a guide row)
        lineup += u16(MUSIC_SID) + b'\x02' + u16(MUSIC_LISTING) + u16(0) + u16(0)
    bat = long_section(0x4a, 0x1000, loop(descriptor(0x47, b'PACE PLAYOUT') + linkage)
                       + loop(transport + loop(namespace + descriptor(0xb1, lineup) + service_list + linkage)), version=ver)
    pat = long_section(0x00, 0, b''.join(u16(c.sid) + u16(0xe000 | c.pmt_pid) for c in chans)
                       + (u16(MUSIC_SID) + u16(0xe000 | MUSIC_PMT) if music else b''), version=ver)
    pmts = [(c.pmt_pid, long_section(0x02, c.sid,
             u16(0xe000 | c.video_pid) + b'\xf0\x00'
             + b'\x02' + u16(0xe000 | c.video_pid) + b'\xf0\x00'
             + b'\x03' + u16(0xe000 | c.audio_pid) + b'\xf0\x00', version=ver)) for c in chans]
    if music:
        pmts.append((MUSIC_PMT, long_section(0x02, MUSIC_SID, u16(0xe000 | MUSIC_PID) + b'\xf0\x00'
                                             + b'\x03' + u16(0xe000 | MUSIC_PID) + b'\xf0\x00', version=ver)))
    tables = [(0x14, tot(when)), (0x10, nit), (0x11, sdt), (0x11, bat), (0, pat)] + pmts
    index_events = []
    for dd in range(days):
        d = when.date() + timedelta(days=dd)
        mjd = (d - EPOCH).days
        for c in chans:
            events = [(dd * 1000 + n + 1, s, l, t) for n, (s, l, t) in enumerate(c.events_utc(d))]
            groups = {}
            for ev in events:
                groups.setdefault(ev[1] // 21600, []).append(ev)
                if dd == 0:
                    index_events.append((c.listing, ev))
            for block, group in groups.items():
                # one section per six-hour block; very short programmes could overflow it
                while group:
                    tables.append((0x30 | (mjd & 7), title_section(0xa0 | block, c.listing, mjd, group[:28], codec)))
                    group = group[28:]
    def index_record(listing, ev):
        return u16(listing) + b'\x0f\xc0\x00' + u16(ev[0]) + b'\x00\x00'
    for letter in range(ord('A'), ord('Z') + 1):
        payload = b''.join(index_record(l, e) for l, e in index_events if e[3][:1].upper() == chr(letter))
        tables.append((0x52, long_section(0xc1, letter, payload[:1000])))
    for genre in (0, 3):
        for block in range(4):
            payload = b''.join(index_record(l, e) for l, e in index_events if e[1] // 21600 == block)
            tables.append((0x52, long_section(0xc1, 0x100 | block << 6 | genre, payload[:1000])))
    today_pid = 0x30 | ((when.date() - EPOCH).days & 7)
    return tables, today_pid


def carousel(tables, today_pid, seconds=8, period_ms=4000):
    """1 Mbit/s SI carousel in the layout tools/sky_streamer.py uses (8 s, every
    table each 4 s, two C1 index sections per 200 ms tick after 80 packets).
    Titles of later days go out once per carousel, spread across the ticks."""
    indices = [(p, s) for p, s in tables if s[0] == 0xc1]
    later = [(p, s) for p, s in tables if 0xa0 <= s[0] <= 0xa3 and p != today_pid]
    rest = [(p, s) for p, s in tables if s[0] != 0xc1 and not (0xa0 <= s[0] <= 0xa3 and p != today_pid)]
    ticks = seconds * 5
    pk = Packetizer()
    data = bytearray()
    for tick in range(ticks):
        start = len(data)
        if tick % (period_ms // 200) == 0:
            for pid, section in rest:
                data += pk.section(pid, section)
        else:
            for pid, section in later[tick::ticks]:
                data += pk.section(pid, section)
        if indices:
            while len(data) - start < 80 * 188:
                data += pk.null()
            for n in range(2):
                pid, section = indices[(tick * 2 + n) % len(indices)]
                data += pk.section(pid, section)
        while len(data) - start < 133 * 188:
            data += pk.null()
    return bytes(data)


# ------------------------------------------------------------------ command line
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('schedule', help='print what each channel shows today')
    s.add_argument('lineup')
    s.add_argument('--day', help='YYYY-MM-DD (UTC), default today')
    a = sub.add_parser('analyse', help='find spot cuts in interstitial folders (cached)')
    a.add_argument('folders', nargs='+')
    pr = sub.add_parser('prepare', help='probe every source and find natural break points (cached)')
    pr.add_argument('lineup')
    args = ap.parse_args()
    settings = load_settings()
    if args.cmd == 'prepare':
        chans, media = load_lineup(args.lineup, settings)
        for c in chans:
            if c.style == 'bbc':
                continue
            for p in c.programmes:
                if p['breaks'] == 'auto' and not p['source'].startswith('plex:'):
                    media.cuts(p['source'])
        print('prepared', sum(len(c.programmes) for c in chans), 'programmes')
        return
    if args.cmd == 'analyse':
        media = Media(settings)
        for runs in interstitial_runs(media, args.folders):
            print(f'{Path(runs[0][0]).name}: {len(runs)} spots, '
                  f'{sum(r[2] for r in runs):.0f} s, lengths ' + ' '.join(f'{r[2]:.0f}' for r in runs[:30]))
        return
    chans, _ = load_lineup(args.lineup, settings)
    d = date.fromisoformat(args.day) if args.day else datetime.now(timezone.utc).date()
    for c in chans:
        print(f'== {c.number} {c.name} ({c.style}, {len(c.runs)} interstitial recordings)')
        for s0, ln, title in c.events_utc(d):
            print(f'  {s0//3600:02d}:{s0//60%60:02d}  {ln//60:4d} min  {title}')


if __name__ == '__main__':
    main()
