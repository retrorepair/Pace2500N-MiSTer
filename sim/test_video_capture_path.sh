#!/bin/bash
# Original U202 -> MPEG decoder DDR -> all four DMA7 image planes.
set -e
cd "$(dirname "$0")/.."
capture_work=${CAPTURE_WORK:-/tmp/pace-capture-test}
capture_rom=${1:-firmware/FLASH_U202.bin}
mkdir -p "$capture_work"
python3 tools/prepare_capture_still.py "$capture_rom" "$capture_work/still.hex"
capture_bytes=$(wc -l < "$capture_work/still.hex")
TOP=tb_video_capture_path TB="sim/tb_mpeg_video.sv sim/tb_video_capture_path.sv" \
 EXTRA="rtl/pace_mpeg_status.sv rtl/pace_video_capture_dma.sv" \
 OBJ="$capture_work/obj" JOBS="${JOBS:-2}" bash sim/build_mpeg.sh
capture_args=()
if [ -n "${CAPTURE_REFERENCE:-}" ]; then
 capture_args+=("+YUV_REF=$CAPTURE_REFERENCE")
fi
"$capture_work/obj/Vtb_video_capture_path" +STILL +ES="$capture_work/still.hex" \
 +BYTES="$capture_bytes" +FIELDS=16 +OUT="$capture_work/field" "${capture_args[@]}"
