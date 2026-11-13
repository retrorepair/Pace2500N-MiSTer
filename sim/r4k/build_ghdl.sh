#!/bin/bash
# Analyse the vendored CPU (rtl/r4k) with GHDL 4.x into sim/r4k/work.
# altera_mf comes from /opt/ghdl-altera (Quartus's altera_mf.vhd compiled for GHDL).
set -e
cd "$(dirname "$0")/../.."
W=sim/r4k/work; mkdir -p $W
G="ghdl -a --std=08 -frelaxed -fsynopsys --workdir=$W -P/opt/ghdl-altera/altera_mf -P/opt/ghdl-altera/lpm -P$W"
for f in RamMLAB dpram SyncFifoFallThroughMLAB; do $G --work=mem rtl/r4k/$f.vhd; done
for f in functions export dpram divider RamMLAB SyncFifoFallThroughMLAB cpu_cdc_fifo cpu_instrcache cpu_datacache \
         cpu_TLB_instr cpu_TLB_data cpu_mul cpu_cop0 cpu ki_cpu_core; do
  $G --work=work rtl/r4k/$f.vhd
done
for f in "$@"; do $G --work=work "$f"; done
echo analysed
