#!/bin/sh
# Runs on the MiSTer: boot the live core, tune a channel from ALL CHANNELS,
# then tune the next one, and report what the firmware routed each time.
#   sh test_two_tunes.sh [launcher.mgl]
# Needs /tmp/mister_keys.py (tools/mister_keys.py) and the live relay running.
MGL=${1:-/media/fat/Pace2500N_V063_Live.mgl}
status() {
  python3 -c "
import os, struct
fd = os.open('/tmp/pace_live.ts', os.O_RDONLY); st = os.pread(fd, 32, 512)
print('routed video %04x audio %04x' % struct.unpack('>HH', st[16:20]))"
}
shot() { echo screenshot > /dev/MiSTer_cmd; sleep 3; echo "screenshot $1: $(ls -t /media/fat/screenshots/Pace2500N_TS/ | head -1)"; }
echo "load_core $MGL" > /dev/MiSTer_cmd
sleep 50
# open the guide and wait for the channel list to come up
n=0
while [ $n -lt 6 ]; do
  n=$((n+1))
  python3 /tmp/mister_keys.py f1:4 enter:10
  python3 - <<EOF && break
import mmap, os, sys
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
ram = mmap.mmap(fd, 0x1000000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x30000000)
sys.exit(0 if ram[:].count(b'DuckTales') else 1)
EOF
done
echo "list after $n visits"
python3 /tmp/mister_keys.py enter:15          # first tune: top of ALL CHANNELS
echo "first tune:"; status; shot first
python3 /tmp/mister_keys.py f1:4 enter:8 down:1.5 enter:15   # second tune: next channel
echo "second tune:"; status; shot second
python3 /tmp/mister_keys.py f1:4 enter:8 down:1.5 down:1.5 enter:15   # third tune
echo "third tune:"; status; shot third
tail -6 /tmp/pace_live_relay.log
