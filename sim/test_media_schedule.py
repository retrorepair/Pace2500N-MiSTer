import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sky_media import Programme, ffmpeg_command, load_schedule, select, timestamp
from pace_channels import Media


class ScheduleTests(unittest.TestCase):
    def test_probe_prefers_english_programme_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / 'clip.mkv'
            clip.touch()
            probe = dict(format=dict(duration='4'), streams=[
                dict(index=0, codec_type='video'),
                dict(index=1, codec_type='audio', tags=dict(language='ces'), disposition=dict(default=1)),
                dict(index=2, codec_type='audio', tags=dict(language='eng', title='Cast commentary')),
                dict(index=3, codec_type='audio', tags=dict(language='eng')),
            ])
            media = Media(dict(ffmpeg='ffmpeg', library_cache=str(root / 'cache.json')))
            with patch('pace_channels.subprocess.run') as run:
                run.return_value.returncode = 0
                run.return_value.stdout = json.dumps(probe)
                self.assertEqual(media.probe(str(clip))['audio_index'], 3)

    def test_half_open_boundaries_and_offsets(self):
        start = timestamp('2002-09-01T12:00:00+01:00')
        a = Programme(start, start + timedelta(hours=1), Path('a.mkv'), 120, 'A')
        b = Programme(a.end, a.end + timedelta(hours=1), Path('b.mkv'), 0, 'B')
        self.assertIs(select([a, b], a.end), b)
        self.assertIsNone(select([a, b], b.end))
        self.assertEqual(start.hour, 11)
        command = ffmpeg_command('ffmpeg', a, start + timedelta(seconds=10), 10000)
        self.assertEqual(command[command.index('-ss') + 1], '130.000000')
        self.assertEqual(command[command.index('-t') + 1], '3590.000000')

    def test_reject_ambiguous_time_and_pid_collisions(self):
        with self.assertRaises(ValueError):
            timestamp('2002-09-01T12:00:00')
        now = datetime.now(timezone.utc)
        p = Programme(now, now + timedelta(hours=1), Path('a.mkv'), 0, 'A')
        with self.assertRaises(ValueError):
            ffmpeg_command('ffmpeg', p, now, 10, video_pid=0x102)

    def test_manifest_requires_provenance_and_nonoverlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);(root / 'a.mkv').touch()
            item = dict(start='2002-09-01T12:00:00Z', end='2002-09-01T13:00:00Z', file='a.mkv')
            path = root / 'schedule.json'
            path.write_text(json.dumps(dict(programmes=[item])))
            with self.assertRaises(ValueError):
                load_schedule(path)
            path.write_text(json.dumps(dict(provenance='synthetic test', programmes=[item, item])))
            with self.assertRaises(ValueError):
                load_schedule(path)
            path.write_text(json.dumps(dict(provenance='synthetic test', programmes=[item])))
            self.assertEqual(load_schedule(path)[0].file, (root / 'a.mkv').resolve())


if __name__ == '__main__':
    unittest.main()
