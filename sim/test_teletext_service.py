import io
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from pace_teletext import HAM, Carousel, page_packets, subtitle_packets, transport_packet, unpack_pes, srt_cues
from pace_subtitles import PESReader, SubtitleRemapper, SubtitleReader, select_source
from pace_geometry import crop_from_samples, detect_pillarbox
from pace_playout import Weaver, pal_video_filter
from pace_hls_subtitles import vtt_cues, WRAP, read_hls


class TeletextTests(unittest.TestCase):
    def test_subtitle_flags_and_text(self):
        rows = subtitle_packets('Hello world\nSecond line', 1)
        self.assertEqual(HAM.index(rows[0][3]) & 7, 0)
        self.assertEqual([HAM.index(v) for v in rows[0][5:7]], [8, 8])
        self.assertEqual(HAM.index(rows[0][10]) & 8, 8)
        self.assertEqual(HAM.index(rows[0][11]) & 3, 3)
        self.assertIn(b'Hello world', bytes(v & 127 for v in rows[1]))
        self.assertTrue(all(v.bit_count() & 1 for row in rows[1:] for v in row[5:]))
        self.assertTrue(all((v & 127) == 32 for row in subtitle_packets('')[1:] for v in row[5:]))

    def test_dvb_pes_roundtrip_and_continuity_loss(self):
        source = page_packets(123, {2: 'TEST'})[:3]
        packet = transport_packet(source, 7)
        self.assertEqual(len(packet), 188)
        self.assertEqual(unpack_pes(packet[4:]), source)
        self.assertEqual(PESReader().packet(packet), source)
        bad = bytearray(packet);bad[53] = 0
        self.assertEqual(len(unpack_pes(bad[4:])), 2)
        self.assertEqual(PESReader().packet(bytes([0] * 188)), [])

    def test_teletext_source_page_remapped_and_other_pages_rejected(self):
        rows = page_packets(777, {22: 'Caption'}, subtitle=True)
        remap = SubtitleRemapper()
        out = [remap.packet(row) for row in rows]
        self.assertEqual(HAM.index(out[0][5]), 8)
        self.assertEqual(HAM.index(out[0][6]), 8)
        self.assertEqual(HAM.index(out[0][3]) & 7, 0)
        self.assertIsNone(remap.packet(page_packets(778, {})[0]))
        self.assertIsNone(remap.packet(rows[22]))

    def test_srt_streaming_and_cue_boundaries(self):
        cues = list(srt_cues(io.StringIO('1\n00:00:01,200 --> 00:00:02,500\n<i>Hello</i>\n\n')))
        self.assertEqual((cues[0].start, cues[0].end, cues[0].text), (1.2, 2.5, 'Hello'))
        reader = SubtitleReader.__new__(SubtitleReader)
        reader.kind = 'text';reader.queue = queue.Queue();reader.queue.put(cues[0]);reader.pending = reader.current = None
        self.assertEqual(reader.text(1.19), '')
        self.assertEqual(reader.text(1.2), 'Hello')
        self.assertEqual(reader.text(2.5), '')

    def test_plex_external_text_preferred_without_global_selection(self):
        media = SimpleNamespace(plex_parts=lambda _: [dict(key='/library/parts/1', Stream=[
            dict(streamType=3, codec='pgs', languageCode='eng'),
            dict(streamType=3, codec='srt', languageCode='eng', key='/library/streams/2')])], plex_url=lambda x: 'https://plex' + x)
        self.assertEqual(select_source(media, 'plex:12')[:3], ('https://plex/library/streams/2', '0:0', 'srt'))

    def test_foreign_text_not_substituted_for_english_bitmap_track(self):
        media = SimpleNamespace(s={}, ffprobe='ffprobe', plex_parts=lambda _: [dict(key='/library/parts/1', Stream=[
            dict(streamType=3, codec='pgs', languageCode='eng', index=8),
            dict(streamType=3, codec='srt', languageCode='ces', index=6)])], plex_url=lambda x: 'https://plex' + x)
        result = SimpleNamespace(returncode=0, stdout=json.dumps({'streams': [
            dict(index=6, codec_type='subtitle', codec_name='srt', tags=dict(language='ces'))]}).encode())
        with patch('pace_subtitles.subprocess.run', return_value=result):
            self.assertIsNone(select_source(media, 'plex:12'))

    def test_carousel_limits_and_raw_subtitles_not_erased(self):
        c = Carousel()
        self.assertIsNotNone(c.packet(0, 'hello'))
        self.assertIsNone(c.packet(.001, 'hello'))
        p = c.packet(.02, None)
        for row in unpack_pes(p[4:]):
            self.assertNotEqual(HAM.index(row[3]) & 7, 0)

    def test_weaver_preserves_av_and_uses_only_spare_slots(self):
        p = transport_packet(page_packets(100, {})[:3])
        c = Carousel()
        weaver = Weaver(b'', (0x200,), lambda t: c.packet(t))
        av = bytes((0x47, 2, 0, 0x10)) + bytes(184)
        self.assertEqual(weaver.packet(av)[4:], av[4:])
        self.assertEqual(weaver.packet()[1:3], p[1:3])

    def test_conservative_pillarbox_consensus(self):
        good = [[(240, 180, 40, 0)] * 8] * 3
        self.assertEqual(crop_from_samples(good, 1920, 1080), (1440, 1080, 240, 0))
        for bad in ([[(320, 180, 0, 0)] * 8] * 3, [[(240, 130, 40, 25)] * 8] * 3,
                    [[(240, 180, 40, 0)] * 8, [(200, 180, 60, 0)] * 8, [(240, 180, 40, 0)] * 8]):
            self.assertIsNone(crop_from_samples(bad, 1920, 1080))
        self.assertTrue(pal_video_filter(True, (1440, 1080, 240, 0)).startswith('crop=1440:1080:240:0,'))

    def test_hls_timestamp_map_and_33_bit_wrap(self):
        text = 'WEBVTT\nX-TIMESTAMP-MAP=LOCAL:07:00:00.000,MPEGTS:900000\n\n07:00:02.000 --> 07:00:04.000 align:start\nHello\n\n'
        cue = next(vtt_cues(text, 10))
        self.assertEqual((cue.start, cue.end, cue.text), (2, 4, 'Hello'))
        wrapped = text.replace('MPEGTS:900000', f'MPEGTS:{WRAP-90000}')
        cue = next(vtt_cues(wrapped, (WRAP-90000)/90000))
        self.assertEqual((cue.start, cue.end), (2, 4))

    def test_hls_rendition_and_relative_uri(self):
        import threading
        stop = threading.Event();out = []
        resources = {
            'https://example.test/master.m3u8': '#EXTM3U\n#EXT-X-MEDIA:TYPE=SUBTITLES,LANGUAGE="en",URI="sub/list.m3u8"',
            'https://example.test/sub/list.m3u8': '#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:15\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\na.vtt\n#EXT-X-ENDLIST',
            'https://example.test/sub/a.vtt': 'WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:900000\n\n00:00:02.000 --> 00:00:03.000\nHello\n\n'}
        with patch('pace_hls_subtitles.get', side_effect=lambda url: (url, resources[url])):
            read_hls('https://example.test/master.m3u8', 10, stop, out.append)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].text, 'Hello')


FFMPEG = shutil.which('ffmpeg') or str(next(ROOT.glob('third_party/ffmpeg-*/bin/ffmpeg.exe'), ''))
FFPROBE = str(Path(FFMPEG).with_name('ffprobe.exe' if FFMPEG.endswith('.exe') else 'ffprobe'))


@unittest.skipUnless(Path(FFMPEG).is_file(), 'Requires FFmpeg')
class RealMediaTests(unittest.TestCase):
    def test_subtitle_extraction_seek_and_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);srt = root / 'source.srt';media = root / 'source.mkv'
            srt.write_text('1\n00:00:01,000 --> 00:00:03,000\nHELLO 888\n\n', encoding='utf-8')
            subprocess.run([FFMPEG, '-v', 'error', '-f', 'lavfi', '-i', 'color=red:size=160x120:rate=25',
                '-i', str(srt), '-t', '4', '-map', '0:v', '-map', '1:s', '-c:v', 'ffv1', '-c:s', 'srt', str(media)], check=True, timeout=15)
            reader = SubtitleReader(SimpleNamespace(ffmpeg=FFMPEG, ffprobe=FFPROBE), str(media), 1, 2)
            reader.thread.join(timeout=15)
            self.assertFalse(reader.thread.is_alive())
            self.assertEqual(reader.text(.1), 'HELLO 888')
            self.assertEqual(reader.text(2.01), '')
            reader.close()
            self.assertIsNotNone(reader.proc.poll())

    def test_real_cropdetect_pillarbox_and_wide_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            clip = Path(directory) / 'pillar.mkv'
            subprocess.run([FFMPEG, '-v', 'error', '-f', 'lavfi', '-i', 'color=red:size=640x480:rate=5',
                '-t', '24', '-vf', 'pad=856:480:108:0:black', '-c:v', 'ffv1', str(clip)], check=True, timeout=20)
            crop = detect_pillarbox(FFMPEG, str(clip), dict(width=856, height=480), 24)
            self.assertIsNotNone(crop)
            self.assertLess(abs(crop[0] - 640), 8)
            self.assertEqual(crop[1], 480)
            result = subprocess.run([FFMPEG, '-v', 'error', '-i', str(clip), '-frames:v', '1', '-vf',
                pal_video_filter(True, crop), '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1'], capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(result.stdout), 720 * 576)
            self.assertGreater(sum(result.stdout[720 * 288:720 * 289]) / 720, 50)


if __name__ == '__main__':
    unittest.main()
