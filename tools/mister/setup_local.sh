#!/bin/sh
# MiSTer Scripts entry for the private ready-to-copy SD card package.
set -e
setup=/media/fat/linux/pace/setup
config=/media/fat/linux/pace/relay.ini
default=
if [ -r "$config" ]; then
    default=$(sed -n 's/^server = //p' "$config")
fi
if command -v dialog >/dev/null 2>&1; then
    address=$(dialog --stdout --inputbox 'Enter the PC address and port shown in Channel Builder. Example: 192.168.1.50:8250' 10 58 "$default") || exit 0
    clear
else
    printf 'PC address and port from Channel Builder [%s]: ' "$default"
    read -r address
    address=${address:-$default}
fi
case "$address" in
    ''|*[!A-Za-z0-9.:-]*) echo 'Enter a PC address such as 192.168.1.50:8250.'; exit 1 ;;
esac
case "$address" in *:*) ;; *) address=$address:8250 ;; esac
port=${address##*:}
case "$port" in ''|*[!0-9]*) echo 'Enter a numeric port, such as 8250.'; exit 1 ;; esac
if ! [ "$port" -ge 1 ] || ! [ "$port" -le 65535 ]; then
    echo 'Enter a port from 1 through 65535.'
    exit 1
fi
cp "$setup/pace_live_relay.py" /tmp/pace_live_relay.py
sh "$setup/install_relay.sh" "$address"
printf '\nSetup complete. Open Pace2500N Live in Other.\nPress Enter to exit. '
read -r ignored
