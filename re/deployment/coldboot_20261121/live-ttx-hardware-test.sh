#!/bin/sh
set -eu
out="/media/fat/linux/pace/re-evidence/coldboot_20261121/V080B-$(date +%H%M%S)"
mkdir -p "$out"
printf '%s\n' "$out"
mister(){ timeout 5 sh -c 'printf "%s\n" "$1" >/dev/MiSTer_cmd' _ "$1"; }
keys(){ python3 /tmp/mister_keys.py 42 "$@"; }
restore(){ mister 'load_core /media/fat/_Other/Pace2500N_V080A_Live.mgl' || true; }
trap restore EXIT
trap 'exit 1' INT TERM
sha256sum /media/fat/_Other/Pace2500N_V080B.rbf > "$out/core.sha256"
python3 /tmp/ut.py 240 --all > "$out/uart.txt" &
uart_pid=$!
mister 'load_core /media/fat/_Other/Pace2500N_V080B_Live.mgl'
sleep 90
python3 /tmp/flashcheck.py > "$out/flashcheck.txt"
keys 59
sleep 10
mister 'screenshot coldV080B-guide-live-text'
wc -l < "$out/uart.txt" > "$out/baseline.idx"
sleep 6
wc -l < "$out/uart.txt" > "$out/live.idx"
keys 87
sleep 5
wc -l < "$out/uart.txt" > "$out/fixture.idx"
sleep 33
wc -l < "$out/uart.txt" > "$out/expired.idx"
keys 87
sleep 3
keys 87
sleep 4
wc -l < "$out/uart.txt" > "$out/cancelled.idx"
# Native All Channels -> tune -> return-to-Guide regression.
keys 28
sleep 8
keys 28
sleep 20
mister 'screenshot coldV080B-live-channel'
keys 59
sleep 10
mister 'screenshot coldV080B-return-guide'
wait "$uart_pid"
python3 /media/fat/linux/pace/verify-live-ttx.py "$out" | tee "$out/result.txt"
grep -q '^PASS ' "$out/result.txt"
trap - EXIT
printf 'PASS V080B left live: TV Text100 index,101 changing clock,888 subtitles\n'
