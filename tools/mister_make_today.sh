#!/bin/sh
# Builds today's synthetic broadcast (SI + OpenTV titles for the current date)
# on the MiSTer, so the replayed stream's title day matches the RTC clock.
# Pure Python standard library; the Huffman table is taken from the firmware's
# own initialised RAM image already on the SD card.
D=/media/fat/games/Pace2500N_TS
cd "$D/broadcast" || exit 1
NOW=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
python3 sky_streamer.py fixture --huffman-ram /media/fat/games/Pace2500N_GUIDE/RAM.bin \
  --full-day --index --seconds 8 --table-period-ms 4000 --utc "$NOW" \
  --output "$D/guide_today.ts.new" > "$D/guide_today.json" 2>&1 && mv -f "$D/guide_today.ts.new" "$D/guide_today.ts"
