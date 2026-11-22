"""Optional live text pages. All remote work is off the playout thread.

100 index,101 receiver test,200 listings,300 BBC headlines,400 weather,
500 MiSTer Main updates. Feed failures retain the last successful content,
labelled with its fetch time. IP location is approximate public-egress location.
"""
import json
import threading
import time
import textwrap
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from pace_teletext import ascii_text, page_packets


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Pace2500N-Teletext/0.8', 'Accept': 'application/json,application/xml,text/xml'})
    with urllib.request.urlopen(request, timeout=6) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError('Feed too large')
    return data


def formatted(page, title, lines, updated=''):
    rows = {1: '\x06' + ascii_text(title)[:39], 24: '\x03' + (updated or '100 INDEX   888 SUBTITLES')[:39]}
    row = 3
    for line in lines:
        for wrapped in textwrap.wrap(ascii_text(line), 39) or ['']:
            if row >= 23:
                break
            rows[row] = wrapped
            row += 1
        if row >= 23:
            break
    return page_packets(page, rows)


class InformationPages:
    def __init__(self, settings, log=lambda _: None):
        self.settings, self.log = settings, log
        self.stop = threading.Event()
        self.content = {}
        self.location = None
        self.revision = 0
        self.thread = None
        if settings.get('teletext_internet', True):
            self.thread = threading.Thread(target=self._run, name='Teletext feeds', daemon=True)
            self.thread.start()

    def _run(self):
        while not self.stop.is_set():
            tasks = ((300, 'BBC NEWS HEADLINES', self.news), (400, 'LOCAL WEATHER', self.weather),
                     (500, 'MISTER MAIN UPDATES', self.mister))
            for number, title, loader in tasks:
                if self.stop.is_set():
                    return
                try:
                    lines = loader()
                    stamp = datetime.now(timezone.utc).strftime('Fetched %d/%m %H:%M UTC')
                    page = formatted(number, title, lines, stamp)
                    self.content = {**self.content, number: page}
                    self.revision += 1
                except Exception as exc:
                    self.log(f'Teletext page {number}: feed unavailable ({type(exc).__name__})')
            self.stop.wait(600)

    def news(self):
        root = ET.fromstring(fetch('https://feeds.bbci.co.uk/news/rss.xml'))
        return ['Source: BBC News', '', *[item.findtext('title', '') for item in root.findall('./channel/item')[:8]]]

    def weather(self):
        manual = self.settings.get('teletext_weather_location')
        if isinstance(manual, dict) and {'latitude', 'longitude'} <= manual.keys():
            loc = manual
        else:
            if self.location is None:
                response = json.loads(fetch('https://ipwho.is/'))
                if response.get('success') is False:
                    raise ValueError('IP location unavailable')
                self.location = {k: response[k] for k in ('latitude', 'longitude', 'city')}
            loc = self.location
        lat, lon = float(loc['latitude']), float(loc['longitude'])
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError('Invalid weather location')
        query = urllib.parse.urlencode(dict(latitude=lat, longitude=lon,
            current='temperature_2m,apparent_temperature,precipitation,wind_speed_10m',
            daily='temperature_2m_max,temperature_2m_min,precipitation_probability_max',
            forecast_days=3, timezone='auto'))
        data = json.loads(fetch('https://api.open-meteo.com/v1/forecast?' + query))
        now, days = data['current'], data['daily']
        lines = [str(loc.get('city') or loc.get('name') or 'Local forecast'),
                 'Approximate public-IP location' if not manual else 'Configured location', '',
                 f"Temperature {now['temperature_2m']} C",
                 f"Feels like  {now['apparent_temperature']} C",
                 f"Wind {now['wind_speed_10m']} km/h", '', 'Date    Low / High C     Rain chance']
        for i, day in enumerate(days['time']):
            lines.append(f"{day[5:]}  {days['temperature_2m_min'][i]} / {days['temperature_2m_max'][i]}   {days['precipitation_probability_max'][i]}%")
        return [*lines, '', 'Source: Open-Meteo.com', 'IP estimate may reflect VPN/ISP city.']

    def mister(self):
        rows = json.loads(fetch('https://api.github.com/repos/MiSTer-devel/Main_MiSTer/commits?per_page=8'))
        if not isinstance(rows, list):
            raise ValueError('MiSTer feed unavailable')
        lines = ['Official Main_MiSTer commits', 'Source: github.com/MiSTer-devel', '']
        for item in rows:
            commit = item['commit']
            lines.append(commit['committer']['date'][:10] + ' ' + commit['message'].splitlines()[0])
        return lines

    def pages(self, listing_lines=(), channel=''):
        now = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
        index = formatted(100, 'PACE TELETEXT - ' + now,
            ['100 Index', '101 Receiver test', '200-249 Channel now and next',
             '300 BBC news headlines', '400 Local weather (public IP)',
             '500 MiSTer Main updates', '888 Subtitles (where available)', '',
             'Watching: ' + channel, 'Use TV Text and page numbers.'])
        test = formatted(101, 'LIVE RECEIVER TEST - ' + now,
            ['This clock changes every second.', 'The broadcast is live, not a ROM page.',
             '\x02GREEN  \x03YELLOW  \x06CYAN  \x07WHITE',
             'Page 888 has subtitle cues, if present.', 'F11 opens the original fixed test.'])
        listing_lines = list(listing_lines) or ['Waiting for channel listings.']
        listings = [formatted(200 + i // 4, f'CHANNELS - NOW AND NEXT {200 + i // 4}', listing_lines[i:i + 4])
                    for i in range(0, min(200, len(listing_lines)), 4)]
        contents = self.content
        return [index, test, *listings, *[contents.get(n, formatted(n, title,
            ['Waiting for feed, or currently offline.', 'Channel playback continues normally.']))
            for n, title in ((300, 'BBC NEWS'), (400, 'WEATHER'), (500, 'MISTER MAIN UPDATES'))]]

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=7)
