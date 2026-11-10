#!/bin/bash
# Build and run the A/V path bench (project root, WSL). Usage: sim/run_av.sh [frames] [ts]
set -e
FRAMES=${1:-4}
TS=${2:-roms/video/server_cbbc.ts}
if [ ! -f sim/av_ts.hex ] || [ "$TS" -nt sim/av_ts.hex ]; then
  python3 - "$TS" <<'PY'
import sys
d = open(sys.argv[1], 'rb').read(8 * 1024 * 1024)
open('sim/av_ts.hex', 'w').write('\n'.join(f'{b:02x}' for b in d) + '\n')
PY
fi
TOP=tb_av TB=sim/tb_av.sv EXTRA="rtl/pace_av_pes.sv rtl/pace_video_mix.sv rtl/pace_pal576i601.sv rtl/mpeg2/mp2/mp2_decode.sv rtl/mpeg2/mp2/bit_fifo.sv rtl/mpeg2/mp2/bit_reader.sv" bash sim/build_mpeg.sh
mkdir -p sim/av_out
timeout 3000 sim/obj_mpeg/Vtb_av +TS=sim/av_ts.hex +BYTES=8388608 +FRAMES=$FRAMES +OUT=sim/av_out/f > sim/av_run.log 2>&1 || true
grep -v "^- \|^$" sim/av_run.log | cut -c1-400 | tail -12
