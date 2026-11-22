#!/bin/sh
# Runs on the MiSTer: install/refresh the Pace live relay and start it.
# Copy this script and pace_live_relay.py to /media/fat/Scripts/, then select
# install_relay from MiSTer's Scripts menu. Enter the PC address shown by the app.
# Command-line use is also supported: sh install_relay.sh PC_ADDRESS:PORT
# Puts the relay in /media/fat/linux/pace/, writes relay.ini, and adds one
# start line to /media/fat/linux/user-startup.sh (once) so it runs at boot.
set -e
D=/media/fat/linux/pace
SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
RELAY_SOURCE=$SCRIPT_DIR/pace_live_relay.py
# Keep compatibility with the earlier SSH instructions.
[ -f "$RELAY_SOURCE" ] || RELAY_SOURCE=/tmp/pace_live_relay.py
if [ ! -f "$RELAY_SOURCE" ]; then
    echo 'Copy pace_live_relay.py into the same folder as install_relay.sh, then try again.'
    exit 1
fi
command -v python3 >/dev/null 2>&1 || { echo 'Python 3 is required on the MiSTer.'; exit 1; }
SERVER=${1:-}
if [ -z "$SERVER" ]; then
    DEFAULT_SERVER=
    if [ -f "$D/relay.ini" ]; then
        DEFAULT_SERVER=$(sed -n 's/^[[:space:]]*server[[:space:]]*=[[:space:]]*//p' "$D/relay.ini" | head -n 1)
    fi
    echo 'Pace 2500N - connect this MiSTer to Channel Builder'
    echo 'Open the app on your PC. Its Playout tab shows the PC address and port.'
    printf 'PC address (for example 192.168.1.10:8250)'
    [ -z "$DEFAULT_SERVER" ] || printf ' [%s]' "$DEFAULT_SERVER"
    printf ': '
    IFS= read -r SERVER || { echo 'No address entered; installation cancelled.'; exit 1; }
    SERVER=${SERVER:-$DEFAULT_SERVER}
fi
case "$SERVER" in
    ''|*[!a-zA-Z0-9._:-]*) echo 'Enter a PC IP address or hostname, optionally followed by :8250.'; exit 1 ;;
esac
case "$SERVER" in *:*) ;; *) SERVER=$SERVER:8250 ;; esac
PORT=${SERVER##*:}
HOST=${SERVER%:*}
case "$PORT" in ''|*[!0-9]*) echo 'The port must be a number from 1 to 65535.'; exit 1 ;; esac
if [ -z "$HOST" ] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo 'Enter a PC address and a port from 1 to 65535.'
    exit 1
fi
mkdir -p "$D"
[ "$RELAY_SOURCE" = "$D/pace_live_relay.py" ] || cp "$RELAY_SOURCE" "$D/pace_live_relay.py"
printf '[relay]\nserver = %s\n' "$SERVER" > "$D/relay.ini"
S=/media/fat/linux/user-startup.sh
LINE='[ -e /media/fat/linux/pace/pace_live_relay.py ] && (python3 /media/fat/linux/pace/pace_live_relay.py >/dev/null 2>&1 &)'
grep -qF 'pace_live_relay.py' $S 2>/dev/null || printf '\n# Pace 2500N live relay (tools/mister/install_relay.sh)\n%s\n' "$LINE" >> $S
# The box's EEPROM save (core V078+, slot S1): create a blank 64 KiB save when
# missing. An existing save (bookings, settings) is never touched.
E=/media/fat/games/Pace2500N_GUIDE/EEPROM.bin
[ -e $E ] || { mkdir -p ${E%/*}; dd if=/dev/zero bs=1024 count=64 2>/dev/null | tr '\000' '\377' > $E; }
for p in $(ps | awk '$3=="python3" && $4 ~ /pace_live_relay/ {print $1}'); do kill $p; done
sleep 1
python3 $D/pace_live_relay.py >/dev/null 2>&1 &
sleep 1
tail -2 /tmp/pace_live_relay.log
printf '\nInstalled. Channel Builder address: %s\n' "$SERVER"
echo 'The relay will start automatically when MiSTer starts.'
echo 'Keep Channel Builder running, then load Pace2500N_V080B_Live.'
if [ "$#" -eq 0 ] && [ -t 0 ]; then
    printf 'Press Enter to return to the MiSTer menu. '
    IFS= read -r REPLY || true
fi
