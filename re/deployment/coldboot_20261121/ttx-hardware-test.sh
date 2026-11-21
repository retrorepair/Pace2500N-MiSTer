#!/bin/sh
# Lab-only fixed page 100. Failure restores the proven V079Z, success leaves
# V080A loaded with ordinary CSync and a fresh F11 test available to the user.
set -eu
out="/media/fat/linux/pace/re-evidence/coldboot_20261121/V080A-$(date +%H%M%S)"
mkdir -p "$out"
printf '%s\n' "$out"
mister(){ timeout 5 sh -c 'printf "%s\n" "$1" >/dev/MiSTer_cmd' _ "$1"; }
keys(){ python3 /tmp/mister_keys.py 42 "$@"; }
restore(){ mister 'load_core /media/fat/_Other/Pace2500N_V079Z_Live.mgl' || true; }
trap restore EXIT
trap 'exit 1' INT TERM
sha256sum /media/fat/_Other/Pace2500N_V080A.rbf > "$out/core.sha256"
python3 /tmp/ut.py 190 --all > "$out/uart.txt" &
uart_pid=$!
mister 'load_core /media/fat/_Other/Pace2500N_V080A_Live.mgl'
sleep 90
python3 /tmp/flashcheck.py > "$out/flashcheck.txt"
keys 59
sleep 10
mister 'screenshot coldV080A-guide-off'
wc -l < "$out/uart.txt" > "$out/baseline.idx"
keys 87
sleep 3
wc -l < "$out/uart.txt" > "$out/active-start.idx"
sleep 6
wc -l < "$out/uart.txt" > "$out/active-end.idx"
mister 'screenshot coldV080A-ttx-on-rgb'
sleep 33
wc -l < "$out/uart.txt" > "$out/expired.idx"
# Verify immediate user cancel as well as the automatic 30-second timeout.
keys 87
sleep 4
keys 87
sleep 4
wc -l < "$out/uart.txt" > "$out/cancelled.idx"
mister 'screenshot coldV080A-normal-sync-restored'
wait "$uart_pid"
python3 /media/fat/linux/pace/verify-ttx-hardware.py "$out" | tee "$out/result.txt"
grep -q '^PASS ' "$out/result.txt"
trap - EXIT
printf 'PASS V080A left loaded, test off; F11 then TV Text page 100\n'
