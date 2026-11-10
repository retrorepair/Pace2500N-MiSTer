"""Optional real FFmpeg/ffprobe test; run under WSL on the development PC."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FFMPEG = shutil.which('ffmpeg')
FFPROBE = shutil.which('ffprobe')
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(FFMPEG and FFPROBE, 'Requires PC ffmpeg and ffprobe')
class MediaIntegration(unittest.TestCase):
    def test_real_mux_and_clean_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / 'source.mkv'
            subprocess.run([FFMPEG, '-v', 'error', '-f', 'lavfi', '-i',
                            'testsrc2=size=160x120:rate=25', '-f', 'lavfi', '-i',
                            'sine=frequency=440:sample_rate=44100', '-t', '3',
                            '-c:v', 'ffv1', '-c:a', 'pcm_s16le', str(clip)], check=True)
            schedule = root / 'schedule.json'
            schedule.write_text(json.dumps(dict(provenance='Generated test bars and 440Hz tone', programmes=[
                dict(title='SYNTHETIC TEST', start='2002-09-01T12:00:00Z',
                     end='2002-09-01T12:00:03Z', file='source.mkv', offset_seconds=0.2)])))
            result = subprocess.run([sys.executable, str(ROOT / 'tools/sky_media.py'), str(schedule),
                                     '--at', '2002-09-01T12:00:00Z', '--seconds', '1',
                                     '--ffmpeg', FFMPEG], capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.assertEqual(result.stdout[0], 0x47)
            self.assertEqual(len(result.stdout) % 188, 0)
            self.assertTrue(all(result.stdout[i] == 0x47 for i in range(0, len(result.stdout), 188)))
            output = root / 'test.ts';output.write_bytes(result.stdout)
            (ROOT / 're/transport/media_smoke.ts').write_bytes(result.stdout)
            (ROOT / 're/transport/media_smoke.log').write_bytes(result.stderr)
            probe = subprocess.run([FFPROBE, '-v', 'error', '-show_programs', '-show_streams',
                                    '-of', 'json', str(output)], capture_output=True, check=True)
            data = json.loads(probe.stdout)
            video, audio = data['streams']
            self.assertEqual((video['codec_name'], video['width'], video['height'], video['id']),
                             ('mpeg2video', 720, 576, '0x200'))
            self.assertEqual((video['r_frame_rate'], video['sample_aspect_ratio']), ('25/1', '16:15'))
            self.assertEqual((audio['codec_name'], audio['sample_rate'], audio['id']), ('mp2', '48000', '0x102'))
            self.assertEqual((audio['channels'], int(audio['bit_rate'])), (2, 192000))
            self.assertEqual(data['programs'][0]['pmt_pid'], 0x1000)
            self.assertEqual(data['programs'][0]['pcr_pid'], 0x200)
            self.assertEqual(data['programs'][0]['program_id'], 1001)
            pcrs = []
            for offset in range(0, len(result.stdout), 188):
                packet = result.stdout[offset:offset + 188]
                if (packet[1] & 31) * 256 + packet[2] != 0x200 or not packet[3] & 0x20:
                    continue
                if packet[4] < 7 or not packet[5] & 0x10:
                    continue
                base = int.from_bytes(packet[6:10], 'big') * 2 + (packet[10] >> 7)
                extension = (packet[10] & 1) * 256 + packet[11]
                pcrs.append(base * 300 + extension)
            self.assertGreater(len(pcrs), 20)
            self.assertTrue(all(0 < b - a <= 1080000 for a, b in zip(pcrs, pcrs[1:])))
            decode = subprocess.run([FFMPEG, '-v', 'error', '-i', str(output), '-f', 'null', '-'],
                                     capture_output=True, check=True)
            self.assertEqual(decode.stderr, b'')
            print(f'Validated {len(result.stdout)} TS bytes: MPEG2 720x576, MP2 48kHz, PAT/PMT/PCR IDs, full decode')


if __name__ == '__main__':
    unittest.main()
