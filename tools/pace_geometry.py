"""Conservative offline detection of 4:3 pillarboxing in a 16:9 source.

Three separated samples must agree; top/bottom cropping, near-black scenes and
arbitrary scene-dependent zooms are rejected. Analysis never runs on the A/V path.
"""
import re
import statistics
import subprocess


def crop_from_samples(samples, width, height, sar=1.):
    if len(samples) < 3 or not 1.70 <= width * sar / height <= 1.90:
        return None
    widths, offsets = [], []
    for observations in samples:
        if len(observations) < 4:
            return None
        cw, ch, x, y = map(lambda i: statistics.median(row[i] for row in observations[-4:]), range(4))
        # Samples are320px wide. Preserve full height, symmetrical sidebars,
        # and only accept a central image already very close to4:3.
        scaled_h = round(height * 320 / width / 2) * 2
        aspect = cw * sar / scaled_h
        if (ch < scaled_h - 4 or y > 2 or x < 24 or abs((320 - cw) / 2 - x) > 3
                or not 1.29 <= aspect <= 1.38):
            return None
        widths.append(cw);offsets.append(x)
    if max(widths) - min(widths) > 4 or max(offsets) - min(offsets) > 3:
        return None
    crop_w = round(statistics.median(widths) * width / 320 / 2) * 2
    crop_x = round((width - crop_w) / 4) * 2
    return (crop_w, height, crop_x, 0)


def detect_pillarbox(ffmpeg, url, video, duration):
    width, height = int(video['width']), int(video['height'])
    sar_text = video.get('sample_aspect_ratio') or '1:1'
    try:
        n, d = map(float, sar_text.split(':'));sar = n / d
    except (ValueError, ZeroDivisionError):
        sar = 1.
    if not 1.70 <= width * sar / height <= 1.90 or duration < 20:
        return None
    samples = []
    for at in (min(60., duration * .15), duration * .45, duration * .75):
        cmd = [ffmpeg, '-hide_banner', '-nostdin', '-rw_timeout', '10000000', '-ss', str(at),
               '-i', url, '-t', '4', '-an', '-sn', '-vf',
               'fps=2,scale=320:-2,cropdetect=limit=16:round=2:reset=0', '-f', 'null', '-']
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                timeout=25, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            return None
        samples.append([tuple(map(int, row)) for row in re.findall(rb'crop=(\d+):(\d+):(\d+):(\d+)', result.stderr)])
    return crop_from_samples(samples, width, height, sar)
