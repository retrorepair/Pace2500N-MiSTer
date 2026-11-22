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
import argparse, hashlib, json, math, os, random, re, subprocess, sys, tempfile, threading, time
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent              # data folder (line-ups, roms/); the app sets it from settings
SOURCE_ROOT = ROOT
FROZEN = getattr(sys, 'frozen', False)          # running as the packaged Windows app
APP_DIR = Path(sys.executable).parent if FROZEN else None
# no console window flashing up for every ffmpeg/ffprobe run from the GUI
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
sys.path.insert(0, str(HERE))
from pace_si import u16, loop, descriptor, long_section, tot, title_section, summary_section, present_following, content_version  # noqa: E402
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
    if portable():
        return APP_DIR / 'data' / 'settings.json'
    base = os.environ.get('APPDATA') or str(Path.home() / '.config')
    return Path(base) / 'Pace2500N' / 'settings.json'


def portable():
    return APP_DIR is not None and (APP_DIR / 'portable.flag').is_file()


PORTABLE_PATHS = ('data_root', 'last_lineup', 'ffmpeg', 'huffman_ram', 'library_cache', 'ytdlp')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value, indent=2):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=indent)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.', suffix='.tmp')
    tmp = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            file.write(payload)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def redact(text):
    return re.sub(r'(?i)(x-plex-token(?:=|%3d))[^&\s\'"]+', r'\1[redacted]', str(text))


def load_settings(log=print):
    p = settings_path()
    try:
        s = read_json(p) if p.exists() else {}
        if not isinstance(s, dict):
            raise ValueError('expected a JSON object')
    except (OSError, ValueError) as e:
        log(f'Could not read settings {p}: {e}. Using defaults for this run.')
        s = {}
    for key in (*PORTABLE_PATHS, 'plex_url', 'plex_token', 'plex_client_id'):
        if key in s and not isinstance(s[key], str):
            log(f'Ignoring invalid {key} setting')
            del s[key]
    for key, default, maximum in (('port', 8250, 65535), ('days', 7, 8)):
        try:
            value = int(s.get(key, default))
            if not 1 <= value <= maximum:
                raise ValueError
        except (TypeError, ValueError):
            log(f'Ignoring invalid {key} setting; using {default}')
            value = default
        s[key] = value
    global ROOT
    ROOT = SOURCE_ROOT
    if portable():
        ROOT = p.parent
        s.setdefault('data_root', str(ROOT))
        if (ROOT / 'lineup.json').is_file():
            s.setdefault('last_lineup', str(ROOT / 'lineup.json'))
        s.setdefault('huffman_ram', str(ROOT / 'firmware' / 'FLASH_U202.bin'))
        for key in PORTABLE_PATHS:
            if s.get(key) and not Path(s[key]).is_absolute():
                s[key] = str(APP_DIR / s[key])
    if s.get('data_root') and Path(s['data_root']).is_dir():
        ROOT = Path(s['data_root'])
    if FROZEN and bundled('ffmpeg.exe') and not Path(s.get('ffmpeg') or 'ffmpeg').is_file():
        s['ffmpeg'] = bundled('ffmpeg.exe')
    s.setdefault('ffmpeg', default_ffmpeg())
    s.setdefault('huffman_ram', str(ROOT / 'firmware' / 'FLASH_U202.bin'))
    s.setdefault('library_cache', str(ROOT / 'roms' / 'library_cache.json'))
    return s


def save_settings(s):
    if portable():
        s = dict(s)
        for key in PORTABLE_PATHS:
            if s.get(key) and Path(s[key]).is_relative_to(APP_DIR):
                s[key] = Path(s[key]).relative_to(APP_DIR).as_posix()
    write_json(settings_path(), s)


def hms(text):
    parts = [int(x) for x in str(text).split(':')]
    while len(parts) < 3:
        parts.append(0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


# ------------------------------------------------------------------ media access
class Media:
    """ffprobe/ffmpeg analysis with a persistent cache, and Plex resolution."""
    cache_lock = threading.RLock()

    def __init__(self, settings):
        self.s = settings
        self.ffmpeg = settings['ffmpeg']
        self.ffprobe = re.sub(r'ffmpeg(\.exe)?$', lambda m: 'ffprobe' + (m.group(1) or ''), self.ffmpeg)
        self.cache_path = Path(settings['library_cache'])
        self.cache = self.read_cache()
        self._keys = {}
        self._dirty = set()
        self._plex_items = {}

    def read_cache(self):
        try:
            raw = read_json(self.cache_path)
            return {k: v for k, v in raw.items() if isinstance(v, dict)} if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self):
        """Merge into the file per entry: other tools (the builder, a prepare run)
        may have added analysis since this process loaded it."""
        with self.cache_lock:
            if not self._dirty:
                return
            disk = self.read_cache()
            for k in self._dirty:
                disk[k] = {**disk.get(k, {}), **self.cache[k]}
            write_json(self.cache_path, disk, indent=1)
            self._dirty.clear()

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

    def plex_metadata(self, rating_key):
        import urllib.request
        base, token = self.s.get('plex_url'), self.s.get('plex_token')
        if not base or not token:
            raise RuntimeError('Plex source used but plex_url/plex_token are not set')
        if not rating_key.isdecimal():
            raise ValueError(f'Invalid Plex rating key: {rating_key}')
        with self.cache_lock:
            cached = self._plex_items.get(rating_key)
        if cached and time.monotonic() < cached[0]:
            return cached[1]
        req = urllib.request.Request(f"{base.rstrip('/')}/library/metadata/{rating_key}?checkFileAvailability=1",
                                     headers={'Accept': 'application/json', 'X-Plex-Token': token})
        with urllib.request.urlopen(req, timeout=10) as response:
            rows = json.load(response).get('MediaContainer', {}).get('Metadata', [])
        if not rows:
            raise ValueError(f'Plex item {rating_key} is unavailable')
        meta = rows[0]
        with self.cache_lock:
            self._plex_items[rating_key] = (time.monotonic() + 300, meta)
        return meta

    def plex_parts(self, rating_key):
        meta = self.plex_metadata(rating_key)
        parts = [m['Part'][0] for m in meta.get('Media', []) if m.get('Part')]
        usable = [p for p in parts if p.get('key', '').startswith('/library/parts/')
                  and all(p.get(s) not in (False, 0, '0', 'false') for s in ('exists', 'accessible'))]
        if not usable:
            raise ValueError('Plex reports the source file is missing or inaccessible on the server' if parts else
                             'Plex item has no playable media')
        return usable

    def plex_part(self, rating_key):
        return self.plex_url(self.plex_parts(rating_key)[0]['key'])

    def plex_url(self, part):
        from urllib.parse import urlencode
        query = urlencode({'X-Plex-Token': self.s['plex_token']})
        sep = '&' if '?' in part else '?'
        return f"{self.s['plex_url'].rstrip('/')}{part}{sep}{query}"

    def summary(self, source):
        """Synopsis for the guide: Plex's summary for plex: sources (fetched once, cached);
        '' for files and when Plex can't be reached (the guide then shows none)."""
        if not source.startswith('plex:'):
            return ''
        hit = self.cache.setdefault(source, {})
        if 'summary' not in hit:
            try:
                meta = self.plex_metadata(source[5:])
            except Exception:
                return ''
            with self.cache_lock:
                summary = meta.get('summary')
                hit['summary'] = summary if isinstance(summary, str) else ''
                self._dirty.add(source)
        return hit['summary'] if isinstance(hit['summary'], str) else ''

    def plex_kind(self, source):
        """('movie' | 'show' | '', [genre tags]) for a plex: source, fetched once and cached.
        An episode's genres are its show's (Plex tags shows, not episodes)."""
        if not source.startswith('plex:'):
            return '', []
        hit = self.cache.setdefault(source, {})
        if 'plex_genres' not in hit:
            try:
                meta = self.plex_metadata(source[5:])
                kind = meta.get('type', '')
                tags = [g.get('tag', '') for g in meta.get('Genre') or [] if isinstance(g, dict)]
                show = meta.get('grandparentRatingKey')
                if kind == 'episode' and show and not tags:
                    shows = self.cache.setdefault(f'plex:{show}', {})
                    if 'plex_genres' not in shows:
                        smeta = self.plex_metadata(str(show))
                        with self.cache_lock:
                            shows['plex_kind'] = 'show'
                            shows['plex_genres'] = [g.get('tag', '') for g in smeta.get('Genre') or []
                                                    if isinstance(g, dict)]
                            self._dirty.add(f'plex:{show}')
                    tags = shows['plex_genres']
            except Exception:
                return '', []
            with self.cache_lock:
                hit['plex_kind'] = 'movie' if kind == 'movie' else 'show'
                hit['plex_genres'] = tags
                self._dirty.add(source)
        return hit.get('plex_kind', ''), hit.get('plex_genres', [])

    def probe(self, source):
        if source.startswith('plex:'):
            error = None
            for part in self.plex_parts(source[5:]):
                url = self.plex_url(part['key'])
                key = source + '|' + part['key']
                try:
                    return {**self.probe_file(source, key, url), 'input': url}
                except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
                    error = exc
            raise error
        return self.probe_file(source, self.key(source), source)

    def probe_file(self, source, k, url):
        hit = self.cache.get(k, {})
        if not isinstance(hit.get('duration'), (float, int)) or not 0 < hit['duration'] < math.inf or 'audio_index' not in hit:
            out = subprocess.run(creationflags=NO_WINDOW, args=[self.ffprobe, '-v', 'error', '-show_entries',
                                  'format=duration:stream=index,codec_type,codec_name,width,height,sample_aspect_ratio:'
                                  'stream_tags=language,title:stream_disposition=default,comment,visual_impaired',
                                  '-of', 'json', url], capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=20)
            if out.returncode:
                raise RuntimeError(redact(f'ffprobe failed for {source}: {out.stderr.strip()}'))
            info = json.loads(out.stdout)
            duration = float(info['format']['duration'])
            if not 0 < duration < math.inf:
                raise ValueError(f'Invalid media duration for {source}')
            audio = [s for s in info.get('streams', []) if s['codec_type'] == 'audio']
            def preference(stream):
                tags, flags = stream.get('tags', {}), stream.get('disposition', {})
                language = tags.get('language', '').lower().split('-')[0]
                secondary = flags.get('comment') or flags.get('visual_impaired') or re.search(
                    r'\b(commentary|audio description|descriptive audio)\b', tags.get('title', ''), re.I)
                return not secondary, language in ('en', 'eng', 'english'), bool(flags.get('default'))
            track = max(audio, key=preference, default={})
            with self.cache_lock:
                hit = self.cache.setdefault(k, {})
                hit.update(duration=duration,
                           audio=bool(audio), audio_index=track.get('index'),
                           video=next(({k: s.get(k) for k in ('codec_name', 'width', 'height', 'sample_aspect_ratio')}
                                       for s in info['streams'] if s['codec_type'] == 'video'), None))
                self._dirty.add(k)
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
                                 capture_output=True, text=True, errors='replace', timeout=600)
            if out.returncode:
                raise RuntimeError(redact(f'ffmpeg analysis failed for {source}: {out.stderr[-1000:].strip()}'))
            black = [(float(a), float(b)) for a, b in
                     re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', out.stderr)]
            silence_start = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', out.stderr)]
            silence_end = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', out.stderr)]
            silence = list(zip(silence_start, silence_end))
            cuts = []
            for a, b in black:
                if any(sa < b + 0.2 and se > a - 0.2 for sa, se in silence):
                    cuts.append(round((a + b) / 2, 3))
            with self.cache_lock:
                hit['cuts'] = cuts
                hit['black'] = [round((a + b) / 2, 3) for a, b in black]
                hit['silence'] = [[round(a, 3), round(b, 3)] for a, b in silence]
                self._dirty.add(k)
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


def usable(length, longest=240.0):
    return 2.0 <= length <= longest


# Longest single segment a break may use. A commercial break is adverts and trailers - 60 s
# at most in the period, the odd 90 s - so anything longer in an off-air recording is
# programme footage the cut finder could not split. BBC-style continuity runs longer.
LONGEST_SPOT = {'itv': 90.0, 'sky': 90.0, 'bbc': 240.0}


def interstitial_runs(media, folders, log=print, longest=240.0):
    """Usable spots of every recording in the sets: lists of (source, start, length)
    that were broadcast back to back. A run is broken wherever a segment is
    unusable (too short/long, e.g. a programme excerpt) or excluded by the user,
    so a break never jumps over it."""
    runs = []
    for folder in folders:
        folder = Path(media.s.get('data_root') or ROOT) / folder
        try:
            excluded = excluded_spots(folder)
        except (OSError, ValueError) as e:
            log(f'{folder.name}: could not read spot exclusions: {e}')
            excluded = set()
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
                if usable(ln, longest) and spot_id(f, a) not in excluded:
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


# The Guide's genre pages list channels by the 3-bit genre in their SDT 0xB2 descriptor
# (radio's 4 is what fills Music & Radio). A line-up channel's "genre" names one of these or
# is "auto": Plex films make a movie channel, otherwise the commonest Plex genre of its
# programmes decides, and anything Plex cannot place is Entertainment.
SKY_GENRES = {'specialist': 1, 'kids': 2, 'entertainment': 3, 'music': 4, 'news': 5, 'movies': 6, 'sports': 7}
PLEX_GENRE = [(('children', 'kids', 'animation'), 'kids'),
              (('documentary', 'news', 'history', 'nature', 'biography', 'travel', 'food'), 'news'),
              (('sport',), 'sports'),
              (('music',), 'music')]


def plex_genre(kind, tags):
    if kind == 'movie':
        return 'movies'
    for words, genre in PLEX_GENRE:
        if any(w in t.lower() for t in tags for w in words):
            return genre
    return 'entertainment'


def channel_genre(cfg, programmes, media):
    name = str(cfg.get('genre') or 'auto').lower()
    if name in SKY_GENRES:
        return SKY_GENRES[name]
    votes = {}
    for p in [p for p in programmes if p['source'].startswith('plex:')][:24]:
        g = plex_genre(*media.plex_kind(p['source']))
        votes[g] = votes.get(g, 0) + 1
    return SKY_GENRES[max(votes, key=votes.get)] if votes else SKY_GENRES['entertainment']


class Channel:
    def __init__(self, index, cfg, media, log=print):
        self.i = index
        self.name = cfg['name']
        self.number = int(cfg.get('number', 101 + index))
        self.style = cfg.get('style', 'bbc')
        self.start = hms(cfg.get('start', '06:00'))
        if self.style not in STYLE or not 0 <= self.start < 86400 or not 1 <= self.number <= 4095:
            raise ValueError('invalid style, broadcast start or channel number')
        self.sid, self.listing = 1001 + index, 3000 + index
        self.pmt_pid, self.video_pid, self.audio_pid = 0x1000 + index, 0x200 + 0x10 * index, 0x102 + 0x10 * index
        self.media = media
        self.programmes = []
        for p in cfg['programmes']:
            try:
                source = p['source']
                if not source.startswith('plex:'):
                    if portable() and not Path(source).is_absolute():
                        source = str(Path(media.s.get('data_root') or ROOT) / source)
                    media.key(source)
                inpoint = float(p.get('inpoint') or 0)
                duration = p.get('duration')
                if source.startswith('plex:') and duration is None:
                    part = media.plex_parts(source[5:])[0]
                    if part.get('duration'):
                        duration = float(part['duration']) / 1000 - inpoint
                dur = float(duration) if duration is not None else media.probe(source)['duration'] - inpoint
                if not 0 <= inpoint < math.inf or not 2 <= dur < math.inf:
                    raise ValueError('invalid duration or in-point')
                summary = p.get('summary')
                if not isinstance(summary, str) or not summary.strip():
                    summary = media.summary(source)
                self.programmes.append(dict(title=p['title'], source=source, inpoint=inpoint, duration=dur,
                                            breaks=p.get('breaks', 'auto'), summary=summary))
            except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.SubprocessError) as e:
                log(redact(f"{self.name}: skipping {p['title']} ({p['source']}): {e}"))
        if not self.programmes:
            raise ValueError('no usable programmes')
        self.runs = interstitial_runs(media, cfg.get('interstitials', []), log,
                                      longest=LONGEST_SPOT.get(self.style, 240.0))
        self.genre = channel_genre(cfg, self.programmes, media)
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
            events.append((slot, t - slot, p['title'], p['summary']))
        if len(self._days) >= 12:
            self._days.pop(next(iter(self._days)), None)
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
        """Guide events for UTC calendar day d: (start, length, title, summary), even seconds, clipped."""
        midnight = datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()
        out = []
        for n in (int((midnight - self.start) // 86400) + x for x in (0, 1)):
            base = n * 86400 + self.start
            for s, ln, title, summary in self.day(n)[1]:
                # the next broadcast day takes over at its start
                a, b = base + s - midnight, min(base + s + ln, base + 86400) - midnight
                a, b = max(a, 0), min(b, 86400)
                a, b = int(a) // 2 * 2, int(b) // 2 * 2
                if b > a and not (out and out[-1][0] == a):
                    out.append((a, b - a, title, summary))
        return out


def read_lineup(path):
    cfg = read_json(path)
    if not isinstance(cfg, dict) or not isinstance(cfg.get('channels'), list):
        raise ValueError('expected a line-up JSON object with a "channels" list')
    if cfg.get('epg_music') is not None and not isinstance(cfg['epg_music'], str):
        raise ValueError('epg_music must be a file path')
    if not isinstance(cfg.get('radio', []), list):
        raise ValueError('radio must be a list of stations')
    for i, channel in enumerate(cfg['channels'], 1):
        if not isinstance(channel, dict) or not isinstance(channel.get('name'), str):
            raise ValueError(f'channel {i} needs a name')
        folders = channel.get('interstitials', [])
        if not isinstance(folders, list) or not all(isinstance(f, str) for f in folders):
            raise ValueError(f'channel {i} needs a list of interstitial folders')
        programmes = channel.get('programmes')
        if not isinstance(programmes, list):
            raise ValueError(f'channel {i} needs a list of programmes')
        for j, p in enumerate(programmes, 1):
            if not isinstance(p, dict) or not all(isinstance(p.get(k), str) and p[k] for k in ('title', 'source')):
                raise ValueError(f'channel {i}, programme {j} needs a title and source')
    return cfg


class RadioStation:
    """A numbered DVB radio service backed by a direct internet audio stream."""

    def __init__(self, cfg):
        self.name = cfg['name'].strip()
        self.number = int(cfg['number'])
        self.url = cfg['url'].strip()
        url = urlsplit(self.url)
        if not self.name or not 800 <= self.number <= 899:
            raise ValueError('radio needs a name and a number between 800 and 899')
        if url.scheme not in ('http', 'https') or not url.hostname:
            raise ValueError('radio needs a direct HTTP or HTTPS audio-stream URL')
        self.i = self.number
        offset = self.number - 800
        self.sid, self.listing = 0x1600 + offset, 0x0e00 + offset
        self.pmt_pid, self.audio_pid = 0x1200 + offset, 0x0700 + offset

    def events_utc(self, _day, sod=None, title=''):
        # The stream supplies a current track, with no reliable duration or
        # future schedule. Display it in the current half-hour Guide cell.
        slot = sod // 1800 * 1800 if title else None
        events = []
        for block in range(0, 86400, 21600):
            cuts = [block, block + 21600]
            if slot is not None and block <= slot < block + 21600:
                cuts.extend((slot, slot + 1800))
            cuts = sorted(set(cuts))
            events.extend((start, end - start, title if start == slot else 'Live Radio', '')
                          for start, end in zip(cuts, cuts[1:]))
        return events


class XMLTVGuides:
    """XMLTV guide files for IPTV channels, fetched on first use and every few hours after,
    shared by every channel that names the same file. Programmes are kept as
    (start, stop, title, description) in UTC seconds. A guide that cannot be fetched leaves its
    channels on "Live TV" and is retried later."""
    REFRESH, RETRY = 3 * 3600, 10 * 60

    def __init__(self):
        self.lock = threading.Lock()
        self.files = {}            # url -> (fetched_at, {channel id: [programmes]})

    def programmes(self, url, channel_id):
        with self.lock:
            when, guide = self.files.get(url, (0, None))
            stale = time.time() - when > (self.REFRESH if guide else self.RETRY)
            if stale:
                self.files[url] = (time.time(), guide)        # one fetch at a time per file
        if stale:
            try:
                fetched = self._fetch(url)
            except Exception:
                fetched = None
            with self.lock:
                if fetched is not None:
                    guide = fetched
                self.files[url] = (time.time(), guide)
        return (guide or {}).get(channel_id, [])

    @staticmethod
    def _fetch(url):
        import gzip, urllib.request
        import xml.etree.ElementTree as ET
        req = urllib.request.Request(url, headers={'User-Agent': 'Pace2500N'})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read(64 << 20)
        if data[:2] == b'\x1f\x8b':
            data = gzip.decompress(data)
        root = ET.fromstring(data)

        def utc(stamp):
            t = datetime.strptime(stamp.strip()[:14], '%Y%m%d%H%M%S')
            off = stamp.strip()[14:].strip() or '+0000'
            sign = -1 if off[0] == '-' else 1
            delta = timedelta(hours=int(off[1:3]), minutes=int(off[3:5])) * sign
            return (t - delta).replace(tzinfo=timezone.utc).timestamp()

        guide = {}
        for prog in root.iter('programme'):
            try:
                start, stop = utc(prog.get('start', '')), utc(prog.get('stop', ''))
            except (ValueError, IndexError):
                continue
            if stop <= start:
                continue
            title = ' '.join((prog.findtext('title') or '').split())
            episode = ' '.join((prog.findtext('sub-title') or '').split())
            desc = ' '.join((prog.findtext('desc') or '').split())
            synopsis = f'{episode}. {desc}' if episode and desc and episode not in desc else desc or episode
            guide.setdefault(prog.get('channel', ''), []).append((start, stop, title, synopsis))
        for progs in guide.values():
            progs.sort()
        return guide


XMLTV = XMLTVGuides()


_guide_index = {'loaded': 0, 'map': None}
_guide_index_lock = threading.Lock()


def iptv_guide_index():
    """iptv-org channel id ("TinyPop.uk", "TinyPop.uk@SD") -> (XMLTV url, guide channel id) for
    the channels i.mjh.nz publishes ready-made XMLTV guides for (Plex, Pluto, Samsung TV Plus,
    Sky Go...). Built from iptv-org's guides.json (~25 MB) once a week and kept as a small file
    beside the settings; {} if it cannot be fetched (channels then show "Live TV")."""
    path = settings_path().with_name('iptv_guides.json')
    with _guide_index_lock:
        if _guide_index['map'] is not None and time.time() - _guide_index['loaded'] < 3600:
            return _guide_index['map']
        index = None
        try:
            if path.exists() and time.time() - path.stat().st_mtime < 7 * 86400:
                index = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            index = None
        if index is None:
            try:
                import urllib.request
                req = urllib.request.Request('https://iptv-org.github.io/api/guides.json',
                                             headers={'User-Agent': 'Pace2500N'})
                with urllib.request.urlopen(req, timeout=60) as r:
                    rows = json.loads(r.read(128 << 20))
                index = {}
                for e in rows:
                    if e.get('site') != 'i.mjh.nz' or '#' not in str(e.get('site_id', '')):
                        continue
                    where, gid = str(e['site_id']).split('#', 1)
                    entry = [f'https://i.mjh.nz/{where}.xml.gz', gid]
                    uk = '/gb' in where.lower() or where.lower().endswith('gb')
                    for key in (e['channel'], f"{e['channel']}@{e.get('feed') or 'SD'}"):
                        if key not in index or uk:          # prefer the UK guide of a channel
                            index[key] = entry
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(index), encoding='utf-8')
            except Exception:
                index = {}
        _guide_index.update(loaded=time.time(), map=index)
        return index


def iptv_guide(cfg):
    """(XMLTV url, channel id) for an IPTV channel: the line-up's "epg"; otherwise the first
    of these that has programmes: the UK guide iptv-org lists for the channel's iptv-org id
    ("tvg_id", kept by the picker), and for a Pluto TV link (jmp2.uk/plu-<id>.m3u8) Pluto's UK
    guide under the link's id (the two ids differ for some channels), and last the guide for
    another region (channels such as Red Bull TV run one feed everywhere)."""
    epg = cfg.get('epg')
    if isinstance(epg, dict) and epg.get('url') and epg.get('id'):
        return str(epg['url']), str(epg['id'])
    candidates, elsewhere = [], []
    tvg = str(cfg.get('tvg_id') or '').strip()
    if tvg:
        index = iptv_guide_index()
        hit = index.get(tvg) or index.get(tvg.split('@')[0])
        if hit:
            (candidates if hit[0].lower().endswith('/gb.xml.gz') else elsewhere).append((hit[0], hit[1]))
    m = re.search(r'jmp2\.uk/plu-([0-9a-f]{24})', cfg.get('iptv', ''))
    if m:
        candidates.append(('https://i.mjh.nz/PlutoTV/gb.xml.gz', m.group(1)))
    candidates += elsewhere
    for url, gid in candidates:
        if XMLTV.programmes(url, gid):
            return url, gid
    return candidates[0] if candidates else None


# iptv-org lists link to anything that streams, including unofficial re-streams of paid
# channels from bare IP addresses. These hosts are the broadcasters' own and the free
# ad-supported platforms that carry channels with their owners' permission.
OFFICIAL_IPTV_HOSTS = ('jmp2.uk/plu-', 'pluto.tv', 'amagi.tv', 'mediatailor.', 'samsung', 'wurl.',
                       'bbci.co.uk', 'akamaized.net/x=4/i=urn:bbc', 'plex.tv', 'stv.tv', 'channel5')
IPTV_GENRES = [(('kids', 'animation', 'children'), 'kids'), (('movie',), 'movies'), (('sport',), 'sports'),
               (('news', 'documentary', 'education', 'science', 'culture', 'weather'), 'news'),
               (('music',), 'music')]
GENRE_BLOCK = {'entertainment': 101, 'movies': 301, 'sports': 401, 'music': 451, 'news': 501, 'kids': 601,
               'specialist': 901}


def iptv_playlist(country='uk', url=None):
    """An iptv-org country list as [{name, url, group, genre, official, notes}] (raw entries;
    `official` marks the hosts above)."""
    import urllib.request
    url = url or f'https://iptv-org.github.io/iptv/countries/{country}.m3u'
    req = urllib.request.Request(url, headers={'User-Agent': 'Pace2500N'})
    with urllib.request.urlopen(req, timeout=20) as r:
        lines = r.read(32 << 20).decode('utf-8', 'replace').splitlines()
    out = []
    for i, line in enumerate(lines):
        if not line.startswith('#EXTINF'):
            continue
        stream = next((x.strip() for x in lines[i + 1:i + 5] if x.strip() and not x.startswith('#')), '')
        if not stream.lower().startswith(('http://', 'https://')):
            continue
        name = line.rsplit(',', 1)[-1].strip()
        notes = ' '.join(re.findall(r'\[[^\]]*\]', name))
        clean = re.sub(r'\s*\[[^\]]*\]|\s*\(\d+p\)', '', name).strip()
        group = (re.search(r'group-title="([^"]*)"', line) or [None, ''])[1]
        tvg_id = (re.search(r'tvg-id="([^"]*)"', line) or [None, ''])[1]
        genre = next((g for words, g in IPTV_GENRES if any(w in group.lower() for w in words)), 'entertainment')
        out.append(dict(name=clean, url=stream, group=group, genre=genre, notes=notes, tvg_id=tvg_id,
                        official=any(h in stream for h in OFFICIAL_IPTV_HOSTS)))
    return out


class LiveChannel:
    """A numbered TV channel fed by a live internet stream (IPTV: HLS or MPEG-TS over HTTP).
    Same service/PID layout as a scheduled channel; nothing is transcoded until the box tunes
    it. The stream has no schedule here, so the Guide shows "Live TV" in each block."""
    style = 'live'
    start = 0
    programmes = ()
    runs = ()

    def __init__(self, index, cfg):
        self.i = index
        self.name = cfg['name'].strip()
        self.number = int(cfg.get('number', 101 + index))
        self.url = cfg['iptv'].strip()
        url = urlsplit(self.url)
        if not self.name or not 1 <= self.number <= 4095:
            raise ValueError('IPTV channel needs a name and a channel number')
        if url.scheme not in ('http', 'https') or not url.hostname:
            raise ValueError('IPTV channel needs an HTTP or HTTPS stream URL')
        self.sid, self.listing = 1001 + index, 3000 + index
        self.pmt_pid, self.video_pid, self.audio_pid = 0x1000 + index, 0x200 + 0x10 * index, 0x102 + 0x10 * index
        self.genre = SKY_GENRES.get(str(cfg.get('genre') or '').lower(), SKY_GENRES['entertainment'])
        self.guide = iptv_guide(cfg)

    def programmes_utc(self):
        return XMLTV.programmes(*self.guide) if self.guide else []

    def events_utc(self, day):
        """The guide's programmes on UTC day `day`, clipped to it and to even seconds, with
        "Live TV" filling whatever the guide does not cover (the stream has no schedule)."""
        midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()
        out, t = [], 0
        for start, stop, title, synopsis in self.programmes_utc():
            a, b = int(max(start - midnight, 0)) // 2 * 2, int(min(stop - midnight, 86400)) // 2 * 2
            if b <= a or a < t:
                continue
            for gap in range(t, a, 21600) if a > t else ():
                end = min(a, (gap // 21600 + 1) * 21600)
                if end > gap:
                    out.append((gap, end - gap, 'Live TV', ''))
            out.append((a, b - a, title or 'Live TV', synopsis))
            t = b
        while t < 86400:
            end = (t // 21600 + 1) * 21600
            out.append((t, end - t, 'Live TV', ''))
            t = end
        return out

    def at(self, utc_seconds):
        n = int(utc_seconds // 86400)
        title = next((p[2] for p in self.programmes_utc() if p[0] <= utc_seconds < p[1]), 'Live TV')
        return (dict(kind='live', title=title, source=self.url, inpoint=0.0, start=0.0, length=86400.0),
                utc_seconds % 86400, n)


def load_radio(cfg, log):
    stations = []
    numbers = {str(c.get('number', '')).strip() for c in cfg['channels']}
    for i, item in enumerate(cfg.get('radio', []), 1):
        try:
            station = RadioStation(item)
            if str(station.number) in numbers:
                raise ValueError('channel number already in use')
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            log(f'Radio station {i} skipped: {exc}')
            continue
        stations.append(station)
        numbers.add(str(station.number))
    return sorted(stations, key=lambda station: station.number)


def load_lineup(path, settings, log=print, *, cfg=None):
    if cfg is None:
        cfg = read_lineup(path)
    media = Media(settings)
    chans = []
    for i, c in enumerate(cfg['channels']):
        if c.get('iptv'):
            try:
                chans.append(LiveChannel(i, c))
            except (KeyError, TypeError, ValueError) as e:
                log(f"{c.get('name', 'channel')}: not broadcast: {e}")
            continue
        if not c.get('programmes'):
            # nothing to schedule: leave it off air rather than fail every channel's guide
            log(f"{c.get('name', 'channel')}: no programmes yet - not broadcast")
            continue
        try:
            chans.append(Channel(i, c, media, log))
        except (OSError, ValueError, TypeError) as e:
            log(redact(f"{c['name']}: not broadcast: {e}"))
    media.save()     # Plex synopses fetched while loading the line-up
    seen = {}
    for c in chans:
        if c.number in seen:
            log(f'WARNING: {c.name} and {seen[c.number]} are both channel {c.number} - the box shows '
                'two rows and only one gets listings; give one of them another number')
        seen.setdefault(c.number, c.name)
    return chans, media


# ------------------------------------------------------------------ guide data (SI)
# The EPG Background Audio service (line-up key "epg_music"): an audio-only radio service as
# Sky broadcast on the EPG (home/default) transponder (SID 4152, audio PID 0x288 per a 2013-15
# channels.conf; unverified for 2002), with its own 0xB1 entry so the box makes a service
# record for it, and the 0x90 background-audio linkage pointing at it.
MUSIC_SID, MUSIC_PMT, MUSIC_PID, MUSIC_LISTING = 4152, 0x10ff, 0x288, 0x0fff


_PLAIN = {'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-',
          '…': '...', ' ': ' ', '½': '1/2', 'æ': 'ae', 'ß': 'ss'}
_encodable = {}


@lru_cache(maxsize=4096)
def guide_text(codec, text, limit, max_chars=None):
    """Text as the box's own Huffman table can carry it: accents and typographic quotes
    folded to plain ASCII, characters the table has no code for dropped, whitespace
    collapsed, and cut at a word so the coded form is at most `limit` bytes and the
    decoded text at most `max_chars` characters."""
    import unicodedata
    s = ''.join(_PLAIN.get(ch, ch) for ch in (text or ''))
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    keep = []
    for ch in ' '.join(s.split()):
        if ch not in _encodable:
            try:
                codec.encode(ch); _encodable[ch] = True
            except ValueError:
                _encodable[ch] = False
        if _encodable[ch]:
            keep.append(ch)
    s = ''.join(keep)
    chars = max_chars or len(s)
    if len(s) <= chars and len(codec.encode(s)) <= limit:
        return s
    while s:
        end = min(len(s) * 9 // 10, chars - 3)
        cut = s.rfind(' ', 0, end)
        s = s[:cut if cut > 0 else end].rstrip(' ,;:')
        if len(s) + 3 <= chars and len(codec.encode(s + '...')) <= limit:
            return s + '...'
    return ''


# Transports. With the EPG Background Audio service on, the line-up is laid out as Sky's was:
# the HOME (default) transponder 11778 V - the box's installed default transponder (EEPROM
# DTFR=11778000) - carries the EPG Background Audio service, and the TV channels are on a
# transponder of their own (12207 V here). Both carry the full guide data. The box then tunes
# between them itself (it retunes only for a service on another transport), and the relay
# reports which one it is on (the firmware's tuned frequency) so playout sends that transport.
ONID = 0x0020
HOME_TSID, CHAN_TSID = 0x0000, 0x0001
HOME_FREQ, CHAN_FREQ = 0x01177800, 0x01220700          # BCD 10 kHz units, as the NIT carries them
SATELLITE = {HOME_TSID: '011778000282a102750002',      # 11778 MHz, 28.2E, V, QPSK, 27.5 Ms/s, 2/3
             CHAN_TSID: '012207000282a102750002'}      # 12207 MHz, same


def transport_of(freq_bcd):
    """The transport the box is tuned to, from the frequency it tuned (BCD, as in the NIT)."""
    return CHAN_TSID if freq_bcd == CHAN_FREQ else HOME_TSID


def record_groups(records, size, budget):
    groups, group, used = [], [], 0
    for record in records:
        length = size(record)
        if used + length > budget:
            groups.append(group)
            group, used = [], 0
        group.append(record)
        used += length
    if group:
        groups.append(group)
    return groups


def event_ids(mjd, starts):
    """Event ids for one service's programmes on day `mjd` (start times in seconds of the day):
    the day and the start minute, (mjd % 22) * 1440 + minute + 1, so a programme keeps its id
    when the rest of the schedule changes (an IPTV guide refresh, an edited line-up). A booking
    in the Personal Planner is kept by event id: numbering programmes by their place in the day
    moved bookings onto other programmes. Programmes starting in the same minute take the next
    free id. At most 31,681: below 0x8000 (the firmware may hold ids as signed 16-bit values;
    the ids it saw before were all small) and unique over 22 days, three weeks beyond the 7-day
    guide."""
    used, out = set(), []
    for start in starts:
        eid = (mjd % 22) * 1440 + int(start) // 60 + 1
        while eid in used:
            eid += 1
        used.add(eid)
        out.append(eid)
    return out


def lineup_tables(now, codec, chans, days, music=False, on=HOME_TSID, stations=(), radio_tracks=None, radio_version=0):
    """Guide data on the home transport and, when split, on the TV/radio transport."""
    when = datetime.fromtimestamp(int(now), timezone.utc)
    sod = int(now) % 86400
    radio_tracks = radio_tracks or {}
    split = bool(music or stations)
    if not split:
        on = HOME_TSID
    # The service tables' version_number follows the channel set, as a broadcaster's does:
    # a box keeps the service list it has (the Guide checkpoint holds one) until the version
    # changes. 1-31, so a line-up never matches the version-0 tables the checkpoint was made with.
    shape = repr([(c.sid, c.number, c.listing, c.name, c.pmt_pid, c.video_pid, c.audio_pid, c.genre) for c in chans]
                 + (['split', MUSIC_SID, 0x90] if music else [])
                 + [(s.sid, s.number, s.listing, s.name) for s in stations] + ['b1 flags 0xE'])
    ver = 1 + int(hashlib.md5(shape.encode()).hexdigest(), 16) % 31
    # The first B2 byte is the number of six-hour listing blocks available
    # from the current block. The grid uses it to bound both right and +24h.
    schedule_blocks = days * 4 - when.hour // 6
    sdt_ver = (ver - 1 + schedule_blocks) % 31 + 1
    radio_version = (radio_version + int(now) // 1800) % 32
    if stations:
        sdt_ver = (sdt_ver - 1 + radio_version) % 31 + 1
    namespace = bytes.fromhex('5f0400000002')
    # per transport: [(service id, service type, its 0xB1 entry)]. B1 entry: service id, type,
    # channel id, channel number (shown by the guide), then number<<4 | flags. The background
    # audio service alone has no guide number.
    # The last field is the number again (12 bits) over four flag bits. Measured on hardware
    # (17 Nov): bit 3 makes a service selectable by typing its number - without it every typed
    # number gives "NNN Channel Unavailable" - and the box shows field 4 as the channel number.
    # Bits 1 and 2 (6) are what the line-up has always sent; bit 0 has no visible effect yet.
    def numbered(service, kind):
        return (service.sid, kind, u16(service.sid) + bytes((kind,)) + u16(service.listing)
                + u16(service.number) + u16(service.number << 4 | 0xE))

    tv = [numbered(c, 1) for c in chans]
    live_radio = [numbered(s, 2) for s in stations]
    background = ([(MUSIC_SID, 2, u16(MUSIC_SID) + b'\x02' + u16(MUSIC_LISTING) + u16(0) + u16(0))]
             if music else [])
    transports = [(HOME_TSID, background), (CHAN_TSID, tv + live_radio)] if split else [(HOME_TSID, tv)]
    services_to_list = [*chans, *stations]
    by_sid = {c.sid: c for c in services_to_list}

    def ts_id(tsid):
        return u16(tsid) + u16(ONID)

    def service_list(services):
        entries = [u16(sid) + bytes((kind,)) for sid, kind, _ in services]
        groups = record_groups(entries, len, 255) or [[]]
        return b''.join(descriptor(0x41, b''.join(group)) for group in groups)

    nit = long_section(0x40, ONID, loop(descriptor(0x40, b'PACE PLAYOUT'))
                       + loop(b''.join(ts_id(t) + loop(descriptor(0x43, bytes.fromhex(SATELLITE[t]))
                                                       + service_list(sv)) for t, sv in transports)),
                       version=ver)

    def sdt_sections(table, tsid, services):
        header = u16(ONID) + b'\xff'
        records = []
        for sid, kind, _ in services:
            if sid == MUSIC_SID:
                name = b'EPG Background Audio'
                desc = namespace + descriptor(0x48, b'\x02\x05BSkyB' + bytes((len(name),)) + name)
            else:
                c = by_sid[sid]
                name = c.name.encode('latin-1', 'replace')[:40]
                desc = namespace + descriptor(0x48, bytes((kind,)) + b'\x05PLAYO' + bytes((len(name),)) + name)
                if kind == 2:
                    current, genre = radio_tracks.get(c.number, ('', ''))[0] or 'Live Radio', 4
                else:
                    it, _, _ = c.at(now)
                    current = it['title'] or next((t for s, l, t, _ in c.events_utc(when.date())
                                                   if s <= now % 86400 < s + l), c.name)
                    genre = c.genre
                desc += descriptor(0xb2, bytes((schedule_blocks, 0, genre << 5))
                                   + codec.encode(guide_text(codec, current, 200)))
            records.append(u16(sid) + b'\xfc' + u16(0x8000 | len(desc)) + desc)
        groups = record_groups(records, len, 1012 - len(header)) or [[]]
        return [long_section(table, tsid, header + b''.join(group), version=sdt_ver,
                             section=i, last=len(groups) - 1) for i, group in enumerate(groups)]

    # SDT "actual" for the transport this stream is, SDT "other" for the rest (all on PID 0x11)
    sdts = [section for t, sv in transports
            for section in sdt_sections(0x42 if t == on else 0x46, t, sv)]
    # 0x91: the box's home service (where Sky with no channel, and boot, go) - the first TV
    # channel. 0x90: the EPG background audio. With Background Music on (setting SSBM) the
    # Guide asks the SI for linkage type 0x90 - native (12,0x24) = 800CB74C -> 800CB69C(0x90),
    # the same lookup (12,0x23) does for 0x91 - so the music service is named by a 0x90 linkage.
    linkage = (descriptor(0x4a, ts_id(CHAN_TSID if split else HOME_TSID) + u16(services_to_list[0].sid) + b'\x91')
               if services_to_list else b'')
    if music:
        linkage += descriptor(0x4a, ts_id(HOME_TSID) + u16(MUSIC_SID) + b'\x90')
    bouquet = loop(descriptor(0x47, b'PACE PLAYOUT') + linkage)
    bat_budget = 1012 - len(bouquet) - 2
    bat_transports = []
    for tsid, services in transports:
        # A B1 takes up to 28 nine-byte entries. Repeat the transport and its
        # private namespace in each section when the line-up fills the loop.
        groups = record_groups(services, lambda _: 12,
                               bat_budget - 6 - len(namespace) - len(linkage) - 14) or [[]]
        for group in groups:
            entries = [entry for _, _, entry in group]
            b1s = record_groups(entries, len, 253) or [[]]
            desc = b''.join(descriptor(0xb1, b'\xff\xff' + b''.join(b1)) for b1 in b1s)
            bat_transports.append(ts_id(tsid) + loop(namespace + desc + service_list(group) + linkage))
    bat_groups = record_groups(bat_transports, len, bat_budget)
    bats = [long_section(0x4a, 0x1000, bouquet + loop(b''.join(group)), version=ver,
                         section=i, last=len(bat_groups) - 1) for i, group in enumerate(bat_groups)]
    here = dict(transports)[on]

    def pmt_pid(sid):
        return MUSIC_PMT if sid == MUSIC_SID else by_sid[sid].pmt_pid

    pat = long_section(0x00, on, b''.join(u16(sid) + u16(0xe000 | pmt_pid(sid)) for sid, _, _ in here), version=ver)
    pmts = []
    for sid, kind, _ in here:
        audio = MUSIC_PID if sid == MUSIC_SID else by_sid[sid].audio_pid
        video = by_sid[sid].video_pid if kind == 1 else None
        streams = b'\x03' + u16(0xe000 | audio) + b'\xf0\x00'
        if video is not None:
            streams = b'\x02' + u16(0xe000 | video) + b'\xf0\x00' + streams
        from pace_teletext import PID as TTX_PID, descriptor_payload
        ttx_desc = descriptor(0x56, descriptor_payload())
        streams += b'\x06' + u16(0xe000 | TTX_PID) + loop(ttx_desc)
        body = u16(0xe000 | (video if video is not None else audio)) + b'\xf0\x00' + streams
        pmts.append((pmt_pid(sid), long_section(0x02, sid, body, version=ver)))
    tables = [(0x14, tot(when)), (0x10, nit)] + [(0x11, x) for x in sdts + bats] + [(0, pat)] + pmts
    index_events = []
    # The full guide (every day, synopses, the A-Z/genre index) is on the home transponder only;
    # another transponder carries just the hours around now - Sky's other transponders had
    # "a couple of hours of Now and Next" for the banner, the 7 days needed the EPG one.
    full = on == HOME_TSID
    if music:
        # Present/following for the background-audio service as well (empty: no programme),
        # as for every other service: after retuning for the Guide the box held the music
        # for ~15 s on the home transponder without them.
        music_table = 0x4e if on == HOME_TSID else 0x4f
        for i in range(2):
            tables.append((0x12, present_following(music_table, MUSIC_SID, HOME_TSID, ONID, 0, i, None)))
    for dd in range(days if full else 1):
        d = when.date() + timedelta(days=dd)
        mjd = (d - EPOCH).days
        for c in services_to_list:
            radio = isinstance(c, RadioStation)
            title, description = radio_tracks.get(c.number, ('', '')) if radio and dd == 0 else ('', '')
            schedule = c.events_utc(d, sod, title) if radio else c.events_utc(d)
            events = [(eid, s, l, guide_text(codec, t, 200))
                      for eid, (s, l, t, _) in zip(event_ids(mjd, [s for s, *_ in schedule]), schedule)]
            # The firmware decodes a 0xB9 synopsis into a 0x101-byte buffer (800CA028 ->
            # 800BECF0 dstmax 0x101): 256 characters and the terminator.
            synopses = [guide_text(codec, description or sm, 255, max_chars=255) for *_, sm in schedule]
            if dd == 0:
                midnight = when.replace(hour=0, minute=0, second=0)
                service_tsid = CHAN_TSID if split else HOME_TSID
                table = 0x4e if service_tsid == on else 0x4f
                entries = [(event_id, midnight + timedelta(seconds=s), l, t, sm)
                           for (event_id, s, l, t), sm in zip(events, synopses) if s + l > sod][:2]
                version = (radio_version if radio else (entries[0][0] if entries else 0)) % 32
                for i in range(2):
                    tables.append((0x12, present_following(table, c.sid, service_tsid, ONID, version, i,
                                                          entries[i] if i < len(entries) else None)))
            groups = {}
            for ev, sm in zip(events, synopses):
                groups.setdefault(ev[1] // 21600, []).append((ev, sm))
                if dd == 0 and full:
                    index_events.append((c.listing, ev, 4 if radio else c.genre))
            # Off the home transponder only the sections holding the programme on air and the
            # next one go out - the very same sections as on the home transponder (same records,
            # section numbers and versions), so the box's full listings are never replaced:
            #  - the box needs the current programme's title record before it starts a channel
            #    (with none, it showed the banner over black and never selected the PIDs);
            #  - a cut-down now/next section under the same table/extension (another version)
            #    replaced the box's full block, and the Guide dropped bookings whose programme
            #    had gone from it;
            #  - whole blocks here made the box spend ~10 s on them before retuning for the
            #    Guide.
            wanted = None if full else {ev[0] for ev in [e for e in events if e[1] + e[2] > sod][:2]}
            if wanted is not None and not wanted:
                groups = {}
            for block, group in groups.items():
                titles = [ev for ev, _ in group]
                # A long section has 1012 bytes of payload, two reserved for MJD.
                chunks = record_groups(titles, lambda e: 13 + len(codec.encode(e[3])), 1010)
                # Theme byte: the channel's genre as Sky's category (high three bits), general
                # sub-genre. The Guide refuses a reminder for a programme stored with theme 0
                # ("The reminder can't be set for this programme"): o-code at 9FC79FC2 calls
                # native (12,0x16) and tests the details' +0x2C, which 800C9F58 copies from
                # the stored record's +4.
                for i, chunk in enumerate(chunks):
                    if wanted is not None and not wanted & {ev[0] for ev in chunk}:
                        continue
                    tables.append((0x30 | (mjd & 7), title_section(0xa0 | block, c.listing, mjd, chunk,
                                                                  codec, i, len(chunks) - 1,
                                                                  version=radio_version if radio and dd == 0 else None,
                                                                  theme=(4 if radio else c.genre) << 5)))
                # OpenTV summaries: same channel id / day / block addressing as the titles,
                # table 0xA8-0xAB on PID 0x40-0x47, descriptor 0xB9 per event id; a section
                # holds as many as fit (a synopsis is up to 255 coded bytes)
                encoded = [(ev[0], codec.encode(sm)) for ev, sm in group if sm]
                chunks = record_groups(encoded, lambda e: 6 + len(e[1]), 1010)
                for i, chunk in enumerate(chunks):
                    if wanted is not None and not wanted & {eid for eid, _ in chunk}:
                        continue
                    tables.append((0x40 | (mjd & 7), summary_section(0xa8 | block, c.listing, mjd, chunk,
                                                                    i, len(chunks) - 1)))
    def index_record(listing, ev):
        return u16(listing) + b'\x0f\xc0\x00' + u16(ev[0]) + b'\x00\x00'

    def add_index(extension, records):
        chunks = record_groups(records, len, 1012) or [[]]
        # The version follows the index's contents, one for all its sections: with a fixed
        # version the box kept the genre/A-Z index it already had, so a genre page went on
        # showing the old schedule's events (only now/next) after the listings changed.
        version = content_version(b''.join(b''.join(chunk) for chunk in chunks))
        for i, chunk in enumerate(chunks):
            tables.append((0x52, long_section(0xc1, extension, b''.join(chunk), version=version,
                                              section=i, last=len(chunks) - 1)))

    for letter in range(ord('A'), ord('Z') + 1) if full else ():
        add_index(letter, (index_record(l, e) for l, e, _ in index_events if e[3][:1].upper() == chr(letter)))
    genres = (0,) + tuple(sorted({g for _l, _e, g in index_events}))
    for genre in genres if full else ():
        for block in range(4):
            add_index(0x100 | block << 6 | genre, (index_record(l, e) for l, e, g in index_events
                                                   if e[1] // 21600 == block and genre in (0, g)))
    today_pid = 0x30 | ((when.date() - EPOCH).days & 7)
    return tables, today_pid


def carousel(tables, today_pid, seconds=8):
    """1 Mbit/s SI carousel in 200 ms ticks.

    PAT/PMT repeat each tick, service tables every 600 ms, and today's titles
    every second. Pace the index, future titles and summaries across the loop.
    """
    service, psi, titles, indices, later = [], [], [], [], []
    for pid, section in tables:
        table_id = section[0]
        if table_id in (0x00, 0x02):
            psi.append((pid, section))
        elif table_id == 0xc1:
            indices.append((pid, section))
        elif 0xa0 <= table_id <= 0xa3 and pid == today_pid:
            titles.append((pid, section))
        elif 0xa0 <= table_id <= 0xab:
            later.append((pid, section))
        else:
            service.append((pid, section))
    # Keep both service and title intervals across the end of the loop.
    ticks = 15 * ((max(seconds * 5, (len(indices) + 1) // 2) + 14) // 15)
    # Later days and synopses: the box fetches a day when it is first shown, one channel and
    # block at a time, so how often each section repeats sets how long "searching for
    # listings" lasts (about 40 s for a day at once a loop). Repeat them as often as the
    # 133-packet tick allows - every 2 s, 4 s, or once a loop for a big line-up.
    def packets(group):
        return sum((len(section) + 1 + 183) // 184 for _pid, section in group)
    steady = packets(psi) + packets(service) / 3 + packets(titles) / 5 + 6
    later_every = next((n for n in (10, 20) if steady + packets(later) / n <= 110), ticks)
    pk = Packetizer()
    data = bytearray()
    for tick in range(ticks):
        start = len(data)
        for pid, section in psi:
            data += pk.section(pid, section)
        if tick % 3 == 0:
            for pid, section in service:
                data += pk.section(pid, section)
        for pid, section in titles[tick % 5::5]:
            data += pk.section(pid, section)
        for pid, section in later[tick % later_every::later_every]:
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
        for s0, ln, title, _ in c.events_utc(d):
            print(f'  {s0//3600:02d}:{s0//60%60:02d}  {ln//60:4d} min  {title}')


if __name__ == '__main__':
    main()
