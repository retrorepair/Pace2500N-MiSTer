"""PC-side scheduled local-media -> DVB MPEG-TS producer.

The current FPGA replay core consumes SI sections, not MPEG PES/audio/video.
This producer prepares that later decoder interface; it is not a live FPGA sink.
Only operator-selected cached files are opened. Run on the PC, not MiSTer's ARM.
"""
import argparse
import json
import math
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Schedule timestamps need an explicit UTC offset')
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class Programme:
    start: datetime
    end: datetime
    file: Path
    offset: float
    title: str


def load_schedule(path):
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not raw.get('provenance'):
        raise ValueError('Schedule needs a provenance label; synthetic data must be labelled')
    result = []
    for item in raw['programmes']:
        start, end = timestamp(item['start']), timestamp(item['end'])
        offset = float(item.get('offset_seconds', 0))
        file = (path.parent / item['file']).resolve()
        if start >= end or not math.isfinite(offset) or offset < 0:
            raise ValueError('Invalid programme duration or source offset')
        if not file.is_file():
            raise ValueError(f'Cached media file does not exist: {file}')
        result.append(Programme(start, end, file, offset, item.get('title', file.stem)))
    result.sort(key=lambda p: p.start)
    if not result or any(a.end > b.start for a, b in zip(result, result[1:])):
        raise ValueError('Schedule is empty or contains overlapping programmes')
    return result


def select(programmes, now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Selection requires an aware clock')
    return next((p for p in programmes if p.start <= now < p.end), None)


def ffmpeg_command(executable, programme, now, seconds, video_pid=0x200,
                   audio_pid=0x102, pmt_pid=0x1000, service_id=1001):
    pids = (video_pid, audio_pid, pmt_pid)
    if len(set(pids)) != 3 or any(not 0x20 <= pid <= 0x1ffe for pid in pids):
        raise ValueError('Three distinct non-reserved PIDs are required')
    if not 1 <= service_id <= 65535 or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Invalid service ID or output duration')
    offset = programme.offset + (now - programme.start).total_seconds()
    if offset < 0 or now >= programme.end:
        raise ValueError('Programme is not active')
    seconds = min(seconds, (programme.end - now).total_seconds())
    return [executable, '-hide_banner', '-loglevel', 'warning', '-nostdin',
            '-re', '-ss', f'{offset:.6f}', '-i', str(programme.file),
            '-t', f'{seconds:.6f}', '-map', '0:v:0', '-map', '0:a:0',
            '-vf', 'scale=720:576:flags=bilinear,setsar=16/15', '-r', '25',
            '-c:v', 'mpeg2video', '-pix_fmt', 'yuv420p', '-g', '12', '-bf', '2',
            '-b:v', '3000k', '-maxrate:v', '4000k', '-bufsize:v', '1835k',
            '-c:a', 'mp2', '-b:a', '192k', '-ar', '48000', '-ac', '2',
            '-streamid', f'0:{video_pid}', '-streamid', f'1:{audio_pid}',
            '-mpegts_pmt_start_pid', str(pmt_pid), '-mpegts_service_id', str(service_id),
            '-mpegts_original_network_id', '32', '-mpegts_transport_stream_id', '1',
            '-mpegts_flags', '+system_b+nit+initial_discontinuity',
            '-metadata', 'service_provider=PACE DIAGNOSTIC',
            '-metadata', 'service_name=LOCAL MEDIA TEST',
            '-muxrate', '5000000', '-pcr_period', '20', '-pat_period', '0.1',
            '-sdt_period', '0.5', '-muxdelay', '0.7', '-f', 'mpegts', 'pipe:1']


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('schedule', type=Path)
    parser.add_argument('--at', help='Historical starting instant with UTC offset; advances in real time')
    parser.add_argument('--seconds', type=float, help='Limit total running time')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--video-pid', type=lambda n: int(n, 0), default=0x200)
    parser.add_argument('--audio-pid', type=lambda n: int(n, 0), default=0x102)
    parser.add_argument('--pmt-pid', type=lambda n: int(n, 0), default=0x1000)
    parser.add_argument('--service-id', type=int, default=1001)
    parser.add_argument('--output', type=Path, help='TS file; default is binary stdout')
    parser.add_argument('--check', action='store_true', help='Print the first command to stderr, without transcoding')
    args = parser.parse_args()
    if args.seconds is not None and (not math.isfinite(args.seconds) or args.seconds <= 0):
        parser.error('--seconds must be finite and positive')
    programmes = load_schedule(args.schedule)
    base = timestamp(args.at) if args.at else datetime.now(timezone.utc)
    started = time.monotonic()
    target = args.output.open('wb') if args.output and not args.check else sys.stdout.buffer
    try:
        while True:
            elapsed = time.monotonic() - started
            if args.seconds is not None and elapsed >= args.seconds:
                return
            now = base + timedelta(seconds=elapsed)
            programme = select(programmes, now)
            if programme is None:
                raise ValueError(f'No scheduled programme at {now.isoformat()}')
            seconds = (programme.end - now).total_seconds()
            if args.seconds is not None:
                seconds = min(seconds, args.seconds - elapsed)
            command = ffmpeg_command(args.ffmpeg, programme, now, seconds,
                                     args.video_pid, args.audio_pid, args.pmt_pid, args.service_id)
            print(f'{programme.title}: offset {programme.offset + (now - programme.start).total_seconds():.3f}s, '
                  f'duration {seconds:.3f}s', file=sys.stderr, flush=True)
            if args.check:
                print(json.dumps(command), file=sys.stderr)
                return
            process = subprocess.Popen(command, stdout=target, stderr=sys.stderr)
            try:
                result = process.wait(timeout=seconds + 3)
            finally:
                stop(process)
            if result:
                raise RuntimeError(f'ffmpeg failed with exit status {result}')
            # An exhausted cached clip is not silently repeated or replaced by
            # unrelated media. A source must actually cover its schedule slot.
            if time.monotonic() - started < elapsed + seconds - 0.5:
                raise RuntimeError('Cached media ended before its scheduled boundary')
            if args.seconds is not None and time.monotonic() - started >= args.seconds - 0.1:
                return
    finally:
        if args.output and not args.check:
            target.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'sky_media: {error}', file=sys.stderr)
        sys.exit(2)
