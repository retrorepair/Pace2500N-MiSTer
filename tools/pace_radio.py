"""Read the current track from Internet radio streams without starting playout."""
import html
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def stream_metadata(url):
    request = Request(url, headers={'Icy-MetaData': '1', 'User-Agent': 'Pace2500N'})
    deadline = time.monotonic() + 6
    with urlopen(request, timeout=4) as response:
        description = response.headers.get('icy-description', '')
        if not description:
            # SomaFM supplies its station blurb after the name in icy-name.
            name = response.headers.get('icy-name', '')
            if name.endswith('[SomaFM]'):
                description = name.removesuffix('[SomaFM]').partition(': ')[2]
        description = ' '.join(html.unescape(description).split())[:500]
        interval = int(response.headers.get('icy-metaint', '0'))
        if not 0 < interval <= 256 * 1024:
            return '', description

        def read(size, keep=False):
            data = bytearray()
            while size:
                if time.monotonic() >= deadline:
                    raise TimeoutError('ICY metadata read timed out')
                chunk = response.read1(min(size, 16384))
                if not chunk:
                    raise EOFError('stream ended before metadata')
                if keep:
                    data.extend(chunk)
                size -= len(chunk)
            return data

        for _ in range(2):
            read(interval)
            size = read(1, keep=True)[0] * 16
            raw = read(size, keep=True).rstrip(b'\x00')
            match = re.search(rb"(?:^|;)\s*StreamTitle='(.*?)';", raw, re.IGNORECASE)
            if match and match[1]:
                try:
                    title = match[1].decode('utf-8')
                except UnicodeDecodeError:
                    title = match[1].decode('cp1252', errors='replace')
                return ' '.join(html.unescape(title).split())[:160], description
    return '', description


class RadioMetadata:
    def __init__(self, stations):
        self.stations = tuple(stations)
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.tracks = {}
        if self.stations:
            threading.Thread(target=self.poll, name='radio metadata', daemon=True).start()

    def refresh(self, station):
        if self.stop.is_set():
            return None
        try:
            title, description = stream_metadata(station.url)
        except HTTPError as exc:
            exc.close()
            return None
        except (OSError, EOFError, HTTPException, ValueError):
            return None
        return station.number, title, description, time.monotonic()

    def poll(self):
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix='ICY') as pool:
            while not self.stop.is_set():
                updates = [track for track in pool.map(self.refresh, self.stations) if track]
                with self.lock:
                    self.tracks.update((number, (title, description, stamp)) for number, title, description, stamp in updates)
                self.stop.wait(20)

    def snapshot(self):
        expires = time.monotonic() - 180
        with self.lock:
            return {number: (title, description) for number, (title, description, stamp) in self.tracks.items()
                    if stamp > expires and (title or description)}
