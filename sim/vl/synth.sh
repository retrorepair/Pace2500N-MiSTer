#!/bin/bash
# Convert the vendored VHDL CPU (rtl/r4k) to Verilog with `ghdl --synth` for the Verilator
# system simulation (sim/vl). Altera RAMs become black boxes (ram_stubs.vhd -> ram_models.v).
#
# `ghdl --synth` (4.1.0 and 6.0.0) dies with an internal error (netlists-utils.adb) on the
# 64-bit address-region compares (`value1 <= x"ffffffffbfffffff"` ...) in cpu.vhd's stage-3
# region decode. That branch runs only when region64 = '1', and region64 is '0' by
# elaboration with ADDR32_ONLY (the Pace configuration, rtl/r4k/pace_r4k_core.vhd), so the
# copy converted here has that dead branch removed. Nothing else is changed.
set -e
GHDL=${GHDL:-$HOME/ghdl6/bin/ghdl}
cd "$(dirname "$0")/../.."
W=${W:-/tmp/vl_work}; rm -rf $W; mkdir -p $W
G="--std=08 -frelaxed -fsynopsys --workdir=$W -P$W"
awk 'skip && $0 == "      else" { skip = 0; print; next }
     skip { next }
     $0 == "      if (region64 = '"'"'1'"'"') then" { print "      if (false) then"; print "         null;"; skip = 1; n++; next }
     { print }
     END { if (n != 1) { print "synth.sh: expected one region64 branch, found " n > "/dev/stderr"; exit 1 } }' \
    rtl/r4k/cpu.vhd > $W/cpu.vhd
$GHDL -a $G --work=mem sim/vl/ram_stubs.vhd rtl/r4k/SyncFifoFallThroughMLAB.vhd
$GHDL -a $G --work=work sim/vl/ram_stubs.vhd
for f in functions export divider SyncFifoFallThroughMLAB cpu_cdc_fifo cpu_instrcache cpu_datacache \
         cpu_TLB_instr cpu_TLB_data cpu_mul cpu_cop0; do
  $GHDL -a $G --work=work rtl/r4k/$f.vhd
done
$GHDL -a $G --work=work $W/cpu.vhd rtl/r4k/pace_r4k_core.vhd
$GHDL --synth $G --out=verilog -gCOUNT_NUM=${COUNT_NUM:-27} -gCOUNT_DEN=${COUNT_DEN:-100} pace_r4k_core > $W/pace_r4k_core.v
ls -la $W/pace_r4k_core.v
