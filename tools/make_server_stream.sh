#!/bin/bash
# Build the Server channel replay: a cut of the local clip (video 0x200, audio 0x102),
# the period EPG background music (0x288, service 4152) and the generated SI carousel.
# Usage (WSL, project root): tools/make_server_stream.sh OUT.ts [utc] [--music-linkage]
set -e
OUT=$1; UTC=${2:-$(date -u +%Y-%m-%dT%H:%M:%S+00:00)}; LINK=$3
FF=/opt/pace-ffmpeg81/bin/ffmpeg
SRC="$(ls /mnt/x/Old\ Kids\ TV/Children*1989.mpg)"
MUSIC=roms/music/mp2/sky_epg_music_2002.mp2
TMP=$(mktemp -d)
python3 tools/sky_streamer.py fixture --huffman-ram re/fpga_guide_checkpoint/RAM.bin --index --seconds 8 \
  --table-period-ms 4000 --channel Server --loop-title "Children's BBC" --loop-seconds 5380 --loop-anchor 18:00 \
  --es-pids 200,102 --music 4152,288 $LINK --utc "$UTC" --output $TMP/si.ts > $TMP/si.json
$FF -hide_banner -loglevel error -nostdin -y -ss 120 -i "$SRC" -i $MUSIC -t 84 \
  -map 0:v:0 -map 0:a:0 -map 1:a:0 -c copy -streamid 0:512 -streamid 1:258 -streamid 2:648 \
  -mpegts_pmt_start_pid 4096 -mpegts_service_id 1001 -muxrate 6250000 -pcr_period 20 -muxdelay 0.7 \
  -f mpegts $TMP/av.ts
python3 tools/sky_mux.py $TMP/av.ts $TMP/si.ts "$OUT" --video 0x200 --audio 0x102 --keep 0x288 --rate 6250000 --max-bytes 67108864
rm -rf $TMP
