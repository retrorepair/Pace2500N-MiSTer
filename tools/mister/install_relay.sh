#!/bin/sh
# Runs on the MiSTer: install/refresh the Pace live relay and start it.
#   sh install_relay.sh PC_ADDRESS:PORT
# Puts the relay in /media/fat/linux/pace/, writes relay.ini, and adds one
# start line to /media/fat/linux/user-startup.sh (once) so it runs at boot.
set -e
SERVER=${1:?usage: install_relay.sh HOST:PORT}
D=/media/fat/linux/pace
mkdir -p $D
cp /tmp/pace_live_relay.py $D/pace_live_relay.py
printf '[relay]\nserver = %s\n' "$SERVER" > $D/relay.ini
S=/media/fat/linux/user-startup.sh
LINE='[ -e /media/fat/linux/pace/pace_live_relay.py ] && (python3 /media/fat/linux/pace/pace_live_relay.py >/dev/null 2>&1 &)'
grep -qF 'pace_live_relay.py' $S 2>/dev/null || printf '\n# Pace 2500N live relay (tools/mister/install_relay.sh)\n%s\n' "$LINE" >> $S
for p in $(ps | awk '$3=="python3" && $4 ~ /pace_live_relay/ {print $1}'); do kill $p; done
sleep 1
python3 $D/pace_live_relay.py >/dev/null 2>&1 &
sleep 1
tail -2 /tmp/pace_live_relay.log
