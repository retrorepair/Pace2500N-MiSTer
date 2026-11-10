#!/bin/bash
# Build the decoder bring-up simulation (run from the project root in WSL).
M=rtl/mpeg2
SRC="$M/framestore.v $M/framestore_request.v $M/framestore_response.v $M/fwft.v $M/getbits.v $M/idct.v $M/iquant.v $M/mem_addr.v $M/mixer.v $M/motcomp.v $M/motcomp_addrgen.v $M/motcomp_dcttype.v $M/motcomp_motvec.v $M/motcomp_picbuf.v $M/motcomp_recon.v $M/mpeg2video.v $M/osd.v $M/pixel_queue.v $M/probe.v $M/read_write.v $M/regfile.v $M/resample.v $M/resample_bilinear.v $M/resample_dta.v $M/reset.v $M/rld.v $M/syncgen.v $M/syncgen_intf.v $M/synchronizer.v $M/vbuf.v $M/vld.v $M/watchdog.v $M/wrappers.v $M/xfifo_sc.v $M/xilinx_fifo.v $M/xilinx_fifo144.v $M/xilinx_fifo216.v $M/xilinx_fifo_dc.v $M/xilinx_fifo_sc.v $M/yuv2rgb.v $M/dvd/resample_addrgen.v $M/dvd/*.sv"
/root/verilator/bin/verilator --binary --timing -Wno-fatal -O2 -j 8 -I$M -I$M/dvd -I$M/mp2 --Mdir sim/obj_mpeg --top-module ${TOP:-tb_mpeg_video} ${TB:-sim/tb_mpeg_video.sv} rtl/pace_mpeg_video.sv $EXTRA $SRC > sim/mpeg_compile.log 2>&1
grep -A4 "%Error" sim/mpeg_compile.log | head -40
ls -la sim/obj_mpeg/V${TOP:-tb_mpeg_video} 2>&1 | tail -1
