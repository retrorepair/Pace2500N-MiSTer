#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
bytes=$(python3 sim/make_teletext_live_vectors.py /tmp)
/root/verilator/bin/verilator --binary --timing --top-module tb_teletext_live \
 -Wno-fatal -Wno-WIDTH -Mdir /tmp/pace-live-ttx-sim sim/tb_teletext_live.sv \
 rtl/pace_teletext_pes.sv rtl/pace_teletext_test.sv -o live-test >/tmp/pace-live-ttx-build.log 2>&1
/tmp/pace-live-ttx-sim/live-test +BYTES=$bytes
cmp /tmp/pace-live-text-expected.hex /tmp/pace-live-text-output.hex
if [ -f /tmp/pace-zvbi/root/usr/include/libzvbi.h ];then
 cc -O2 -I/tmp/pace-zvbi/root/usr/include sim/decode_teletext_live.c \
 -L/tmp/pace-zvbi/root/usr/lib/x86_64-linux-gnu -Wl,-rpath,/tmp/pace-zvbi/root/usr/lib/x86_64-linux-gnu \
 -lzvbi -o /tmp/pace-live-zvbi-decode
 /tmp/pace-live-zvbi-decode /tmp/pace-live-text-output.hex
fi
