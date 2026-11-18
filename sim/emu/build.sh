#!/bin/bash
# Build the top-level start-up simulation (sim/emu/tb_emu.sv). Needs the GHDL output of
# sim/vl/synth.sh in $W (as sim/vl/build.sh). Output: $OBJ/Vtb_emu
set -e
cd "$(dirname "$0")/../.."
W=${W:-/tmp/vl_work}; OBJ=${OBJ:-/tmp/vl_emu}
[ -f $W/pace_r4k_core_p.v ] || { echo "run sim/vl/build.sh first (GHDL output in $W)"; exit 1; }
python3 sim/vl/vl_patch.py $W
verilator --binary --timing --top-module tb_emu -Mdir $OBJ -j 12 --build-jobs 12 \
    -Wno-fatal -Wno-lint -Wno-style -Wno-TIMESCALEMOD -Wno-MULTIDRIVEN -Wno-INITIALDLY -Wno-PINMISSING \
    -O3 --x-assign fast --x-initial fast -CFLAGS "-O2" -I. +define+MISTER_RAM2=1 \
    sim/emu/tb_emu.sv sim/emu/stubs.sv \
    rtl/Pace2500N_Transport.sv rtl/pace_r4k.sv $W/pace_r4k_core_p.v sim/vl/ram_models.v \
    rtl/pace_debug_uart.sv rtl/pace_boot_monitor.sv rtl/pace_keyboard_remote.sv \
    $W/pace_guide_peripherals.sv rtl/pace_guide_blitter.sv rtl/pace_guide_video601.sv rtl/pace_pal576i601.sv \
    rtl/pace_ts_replay.sv rtl/pace_section_demux.sv rtl/pace_transport_dma.sv rtl/pace_mmio_response.sv \
    rtl/pace_ts_load_tracker.sv rtl/pace_tot_clock.sv rtl/pace_av_pes.sv rtl/pace_guide_still.sv \
    rtl/pace_mpeg_status.sv rtl/pace_video_mix.sv rtl/pace_ts_stream.sv rtl/pace_eeprom_save.sv
ls -la $OBJ/Vtb_emu
