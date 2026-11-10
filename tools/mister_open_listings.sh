#!/bin/sh
# Runs on MiSTer: load a launcher, then open ALL CHANNELS until the decoded
# programme title ($2) appears in guest RAM (the Guide needs a few visits).
MGL=$1; TITLE=$2
echo "load_core $MGL" > /dev/MiSTer_cmd
sleep 42
n=0
while [ $n -lt 8 ]; do
  n=$((n+1))
  python3 /tmp/mister_keys.py enter:9
  if python3 - "$TITLE" <<'PY'
import mmap, os, sys
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
ram = mmap.mmap(fd, 0x1000000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0x30000000)
sys.exit(0 if ram[:].find(sys.argv[1].encode()) >= 0 else 1)
PY
  then echo "listings up after $n opens"; exit 0; fi
  python3 /tmp/mister_keys.py esc:2
done
echo "listings not up after $n opens"; exit 1
