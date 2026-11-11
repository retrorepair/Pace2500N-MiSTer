#!/usr/bin/env python3
"""Write a mock three-channel line-up (BBC1 / ITV / Sky One) from the media on
the X: share, for trying the playout chain. Output: roms/lineup_mock.json."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = Path('X:/Old Kids TV')
TV = Path('X:/TV Shows')


def eps(folder, pattern, title, limit):
    files = sorted(f for f in Path(folder).glob(pattern) if f.suffix.lower() in ('.mkv', '.avi', '.mp4', '.mpg'))
    return [{'title': title, 'source': f.as_posix()} for f in files[:limit]]


def first(folder, glob):
    return next(Path(folder).glob(glob)).as_posix()


friends = next((TV / 'Friends').glob('Friends.S01-S10*'))
lineup = {'channels': [
    {'name': 'BBC1', 'number': 101, 'style': 'bbc', 'start': '06:00',
     'interstitials': ['roms/interstitials/bbc1_1988_89'],
     'programmes': [
         {'title': "Children's BBC", 'source': first(OLD, "Children's BBC*1989.mpg")},
         {'title': 'BBC1 Christmas Eve', 'source': first(OLD, 'BBC1 Christmas Eve*.mpg')},
     ]},
    {'name': 'ITV', 'number': 103, 'style': 'itv', 'start': '06:00',
     'interstitials': ['roms/interstitials/itv_1987_89'],
     'programmes': (
         [{'title': 'CITV', 'source': first(OLD, '1992-09-04 CITV*.mpg')}]
         + eps(TV / 'DuckTales' / 'Season 1', '*', 'DuckTales', 6)
         + [{'title': 'The Chart Show', 'source': first(OLD, 'ITV Chart Show*.avi')}]
         + eps(TV / 'DuckTales' / 'Season 2', '*', 'DuckTales', 4))},
    {'name': 'Sky One', 'number': 106, 'style': 'sky', 'start': '06:00',
     'interstitials': ['roms/interstitials/sky1_1993_94'],
     'programmes': (
         eps(friends / 'Friends.S01.1080p.Bluray.x265-HiQVE', '*', 'Friends', 6)
         + eps(TV / 'Law & Order 1990 Seasons 1 to 23 Complete Mixed x264 [i_c]' / 'Season 1', '*', 'Law & Order', 3))},
]}
out = ROOT / 'roms' / 'lineup_mock.json'
out.write_text(json.dumps(lineup, indent=1))
print(out, sum(len(c['programmes']) for c in lineup['channels']), 'programmes')
