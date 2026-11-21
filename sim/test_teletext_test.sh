#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/make_teletext_test_page.py
/root/verilator/bin/verilator --binary --timing --top-module tb_teletext_test \
 -Wno-fatal -Wno-WIDTH -Mdir /tmp/pace-ttx-sim sim/tb_teletext_test.sv rtl/pace_teletext_test.sv -o ttx-test \
 >/tmp/pace-ttx-compile.log 2>&1
/tmp/pace-ttx-sim/ttx-test
# Optional independent decoder; extracted Ubuntu packages, no system changes.
if [ -f /tmp/pace-zvbi/root/usr/include/libzvbi.h ];then
 cc -Wall -Wextra -O2 -I/tmp/pace-zvbi/root/usr/include sim/decode_teletext_test.c \
  -L/tmp/pace-zvbi/root/usr/lib/x86_64-linux-gnu -Wl,-rpath,/tmp/pace-zvbi/root/usr/lib/x86_64-linux-gnu \
  -lzvbi -o /tmp/pace-zvbi-decode
 /tmp/pace-zvbi-decode /tmp/pace-ttx-packets.hex
fi
for fp in 0 1;do for mv in 0 1;do for tt in 0 1;do
 iverilog -g2012 -s tb_debug_uart_pending -Ptb_debug_uart_pending.EXTRA_FP=$fp \
  -Ptb_debug_uart_pending.EXTRA_VIDEO=$mv -Ptb_debug_uart_pending.EXTRA_TTX=$tt \
  -o /tmp/pace-ttx-uart sim/tb_debug_uart_pending.sv rtl/pace_debug_uart.sv
 vvp /tmp/pace-ttx-uart
done;done;done
