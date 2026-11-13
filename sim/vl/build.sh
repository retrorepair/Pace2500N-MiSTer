#!/bin/bash
# Build the Verilator system simulation (see tb_sys.sv). Run from anywhere; needs
# Verilator 5 and GHDL 6 (sim/vl/synth.sh). Output: /tmp/vl_obj/Vtb_sys
set -e
cd "$(dirname "$0")/../.."
W=${W:-/tmp/vl_work}; OBJ=${OBJ:-/tmp/vl_obj}
[ "$1" = nosynth ] || W=$W bash sim/vl/synth.sh
# ghdl --synth fixes the generics at elaboration; the wrapper still passes them.
sed 's/^module pace_r4k_core$/module pace_r4k_core #(parameter COUNT_NUM = 27, parameter COUNT_DEN = 100)/' \
    $W/pace_r4k_core.v > $W/pace_r4k_core_p.v
python3 sim/vl/vl_patch.py $W
verilator --binary --timing --top-module tb_sys -Mdir $OBJ -j 12 --build-jobs 12 \
    -Wno-fatal -Wno-lint -Wno-style -Wno-TIMESCALEMOD -Wno-MULTIDRIVEN -Wno-INITIALDLY \
    -O3 --x-assign fast --x-initial fast -CFLAGS "-O2" -I. \
    sim/vl/tb_sys.sv rtl/pace_r4k.sv $W/pace_r4k_core_p.v sim/vl/ram_models.v \
    rtl/pace_mmio_response.sv $W/pace_guide_peripherals.sv rtl/pace_guide_blitter.sv \
    rtl/pace_section_demux.sv rtl/pace_mpeg_status.sv
ls -la $OBJ/Vtb_sys
# The shadow check (tb_shadow.sv): /tmp/vl_obj_sh/Vtb_shadow
verilator --binary --timing --top-module tb_shadow -Mdir ${OBJ}_sh -j 12 --build-jobs 12 \
    -Wno-fatal -Wno-lint -Wno-style -Wno-TIMESCALEMOD -Wno-MULTIDRIVEN -Wno-INITIALDLY \
    -O3 --x-assign fast --x-initial fast -CFLAGS "-O2" -I. \
    sim/vl/tb_shadow.sv $W/pace_firmware_cpu.sv rtl/pace_bootram.sv rtl/pace_bootrom.sv rtl/pace_muldiv.sv
ls -la ${OBJ}_sh/Vtb_shadow
