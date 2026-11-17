#!/usr/bin/env bash
# Run from the repository root with Verilator on PATH.
set -euo pipefail

work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
mp2=rtl/mpeg2/mp2

verilator --binary --timing -Wno-fatal -O2 -j 4 -I"$mp2" \
    --Mdir "$work/build" --top-module tb_mp2_recovery \
    sim/tb_mp2_recovery.sv "$mp2/mp2_decode.sv" \
    "$mp2/bit_fifo.sv" "$mp2/bit_reader.sv" > "$work/build.log" 2>&1 || {
    cat "$work/build.log" >&2
    exit 1
}
"$work/build/Vtb_mp2_recovery"
