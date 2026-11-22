"""Bounded HLS WebVTT reader with RFC8216 timestamp-map/33-bit-wrap handling.

Some FFmpeg HLS inputs advertise WebVTT yet do not emit its packets. Read that
text rendition directly, using the selected video start PTS as the cue origin.
No video segments are downloaded, no OCR or subtitle-language mutation.
"""
import re
import urllib.request
from urllib.parse import urljoin, urlsplit
from collections import deque
from pace_teletext import Cue, ascii_text, timestamp

WRAP = 1 << 33

class NotHLS(ValueError):
    pass


def get(url):
    if urlsplit(url).scheme not in ('http', 'https'):
        raise ValueError('Subtitle URL must be HTTP(S)')
    request = urllib.request.Request(url, headers={'User-Agent': 'Pace2500N-Teletext/0.8'})
    with urllib.request.urlopen(request, timeout=6) as response:
        data = response.read(2_000_001)
        final = response.geturl()
    if len(data) > 2_000_000:
        raise ValueError('Subtitle resource too large')
    return final, data.decode('utf-8-sig', 'replace')


def attributes(line):
    return {key: quoted if quoted else bare for key, quoted, bare in
            re.findall(r'([A-Z0-9-]+)=(?:"([^"]*)"|([^,]*))', line)}


def vtt_cues(text, video_start):
    local = re.search(r'LOCAL:([0-9:.]+)', text)
    mpeg = re.search(r'MPEGTS:(\d+)', text)
    anchor = timestamp(local[1]) if local else 0.
    ticks = int(mpeg[1]) if mpeg else 0
    for block in re.split(r'\r?\n\s*\r?\n', text):
        rows = block.splitlines()
        for i, row in enumerate(rows):
            match = re.search(r'((?:\d+:)?\d{2}:\d{2}[.,]\d+)\s*-->\s*((?:\d+:)?\d{2}:\d{2}[.,]\d+)', row)
            if not match:
                continue
            a, b = [timestamp(v if v.count(':') == 2 else '00:' + v) for v in match.groups()]
            start_pts = ticks + (a - anchor) * 90000
            start = ((start_pts - video_start * 90000 + WRAP / 2) % WRAP - WRAP / 2) / 90000
            end = start + b - a
            if 0 < b - a <= 3600 and end > 0:
                yield Cue(max(0., start), end, ascii_text(' '.join(rows[i + 1:])))
            break


def read_hls(url, video_start, stop, publish):
    base, master = get(url)
    if not master.lstrip().startswith('#EXTM3U'):
        raise NotHLS('Not an HLS playlist')
    renditions = [attributes(line) for line in master.splitlines()
                  if line.startswith('#EXT-X-MEDIA:') and 'TYPE=SUBTITLES' in line]
    candidates = [r for r in renditions if r.get('LANGUAGE', '').lower() in ('en', 'eng', '') and r.get('URI')]
    if not candidates:
        raise ValueError('No English HLS text rendition')
    rendition = next((r for r in candidates if r.get('DEFAULT') == 'YES'), candidates[0])
    url = urljoin(base, rendition['URI'])
    seen = deque(maxlen=256)
    cues_seen = deque(maxlen=512)
    first = True
    while not stop.is_set():
        base, playlist = get(url)
        if any(line.startswith('#EXT-X-KEY:') and 'METHOD=NONE' not in line for line in playlist.splitlines()):
            raise ValueError('Encrypted WebVTT rendition not supported')
        segments = [line.strip() for line in playlist.splitlines() if line.strip() and not line.startswith('#')]
        sequence = re.search(r'#EXT-X-MEDIA-SEQUENCE:(\d+)', playlist)
        segments = [(int(sequence[1]) + i if sequence else i, segment) for i, segment in enumerate(segments)]
        target = re.search(r'#EXT-X-TARGETDURATION:(\d+)', playlist)
        if first:
            segments = segments[-3:]
            first = False
        for sequence, segment in segments:
            segment_url = urljoin(base, segment)
            if (sequence, segment_url) in seen:
                continue
            if stop.is_set():
                return
            _, text = get(segment_url)
            for cue in vtt_cues(text, video_start):
                signature = (round(cue.start, 3), round(cue.end, 3), cue.text)
                if signature not in cues_seen:
                    publish(cue)
                    cues_seen.append(signature)
            seen.append((sequence, segment_url))
        if '#EXT-X-ENDLIST' in playlist:
            return
        stop.wait(max(.5, min(3., int(target[1]) / 2 if target else 2.)))
