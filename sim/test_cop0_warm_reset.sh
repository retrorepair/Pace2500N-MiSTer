#!/bin/bash
# Isolated CP0 regression: no firmware, checkpoint, Quartus or simulator cache.
set -euo pipefail
cd "$(dirname "$0")/.."
GHDL=${GHDL:-$HOME/ghdl6/bin/ghdl}
W=$(mktemp -d /tmp/pace-cop0-reset.XXXXXX)
trap 'rm -rf -- "$W"' EXIT
G=(--std=08 -frelaxed -fsynopsys --workdir="$W" -P"$W")
"$GHDL" -a "${G[@]}" --work=mem sim/vl/ram_stubs.vhd
"$GHDL" -a "${G[@]}" rtl/r4k/export.vhd rtl/r4k/cpu_TLB_instr.vhd \
    rtl/r4k/cpu_TLB_data.vhd rtl/r4k/cpu_cop0.vhd sim/tb_cop0_warm_reset.vhd
"$GHDL" --elab-run "${G[@]}" tb_cop0_warm_reset --assert-level=error --stop-time=1us
