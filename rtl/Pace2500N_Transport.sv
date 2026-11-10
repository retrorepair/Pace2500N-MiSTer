// SPDX-License-Identifier: GPL-3.0-only
// FPGA-only firmware execution, explicit diagnostic checkpoint resume.
module emu (
`include "sys/emu_ports.vh"
);
localparam CONF_STR={"Pace2500N_TS;;","F0,BIN,Load FLASH_U202.bin;","F1,BIN,Load RAM checkpoint;","F2,BIN,Load CPU state;","F3,TS,Load SI replay (1MiB max);","O3,Display,Guide,Diagnostics;","O4,Diagnostic RF lock,From TS,Off;","O5,Broadcast clock (TOT),MiSTer RTC,TS file;","-;","R0,Reset (reload checkpoint);","V,0.5.3 burst blitter, I-cache"};
wire clk_sys,clk_video,pll_locked;
pll pll(.refclk(CLK_50M),.rst(1'b0),.outclk_0(clk_sys),.outclk_1(clk_video),.locked(pll_locked));
// Unused platform interfaces: MiSTer sys_top remains responsible for
// pinout, HPS bus, and video/composite sync on the analogue board.
assign ADC_BUS='Z;
assign USER_OUT='1;
assign {UART_RTS,UART_DTR}=2'b00;
assign {SD_SCK,SD_MOSI,SD_CS}='Z;
assign {SDRAM_DQ,SDRAM_A,SDRAM_BA,SDRAM_CLK,SDRAM_CKE,
        SDRAM_DQML,SDRAM_DQMH,SDRAM_nWE,SDRAM_nCAS,
        SDRAM_nRAS,SDRAM_nCS}='Z;
`ifdef MISTER_DUAL_SDRAM
assign {SDRAM2_DQ,SDRAM2_A,SDRAM2_BA,SDRAM2_CLK,SDRAM2_nRAS,
        SDRAM2_nCAS,SDRAM2_nWE,SDRAM2_nCS}='Z;
`endif
`ifdef MISTER_FB
assign FB_EN=1'b0;
assign FB_FORMAT=5'd0;
assign FB_WIDTH=12'd0;
assign FB_HEIGHT=12'd0;
assign FB_BASE=32'd0;
assign FB_STRIDE=14'd0;
assign FB_FORCE_BLANK=1'b0;
`ifdef MISTER_FB_PALETTE
assign {FB_PAL_CLK,FB_PAL_ADDR,FB_PAL_DOUT,FB_PAL_WR}='0;
`endif
`endif
assign VGA_SL=2'b00;
assign VGA_SCALER=1'b0;
assign VGA_DISABLE=1'b0;
assign HDMI_FREEZE=1'b0;
assign HDMI_BLACKOUT=1'b0;
assign HDMI_BOB_DEINT=1'b1; // Interlaced field bob for HDMI fallback
assign LED_POWER=2'b00;
assign LED_DISK=2'b00;
assign AUDIO_L=16'd0;
assign AUDIO_R=16'd0;
assign AUDIO_S=1'b1;
assign AUDIO_MIX=2'b00;
assign VIDEO_ARX=13'd4;
assign VIDEO_ARY=13'd3;
assign BUTTONS=2'b00;
assign DDRAM_CLK=clk_sys;

wire [1:0] buttons;
wire [127:0] status;
wire [10:0] ps2_key;
wire [64:0] rtc;
wire ioctl_download,ioctl_wr;
wire [15:0] ioctl_index,ioctl_dout;
wire [26:0] ioctl_addr;
wire ioctl_wait;
hps_io #(.CONF_STR(CONF_STR),.WIDE(1)) io (
 .clk_sys(clk_sys),.HPS_BUS(HPS_BUS),.buttons(buttons),.status(status),.status_in(status),
 .status_set(1'b0),.status_menumask(16'h0000),.ps2_key(ps2_key),.RTC(rtc),
 .video_rotated(1'b0),.new_vmode(1'b0),
 .ioctl_download(ioctl_download),.ioctl_wr(ioctl_wr),.ioctl_index(ioctl_index),
 .ioctl_addr(ioctl_addr),.ioctl_dout(ioctl_dout),.ioctl_wait(ioctl_wait),
 .ioctl_upload_req(1'b0),.ioctl_upload_index(8'h00),.ioctl_din(16'h0000),
 .sd_lba('{32'd0}),.sd_blk_cnt('{6'd0}),.sd_rd(1'b0),.sd_wr(1'b0),.sd_buff_din('{16'h0000}),.sd_buff_wr());
wire core_reset=!pll_locked || RESET || buttons[1] || status[0];
reg loaded_flash=0,loaded_ram=0,loaded_state=0;
reg previous_download=0;reg [15:0] last_download_index=0;
reg [26:0] last_download_address=0;
reg [15:0] state_high=0;
wire loaded_stream;wire [23:0] stream_length;
wire stream_loading=ioctl_download && ioctl_index==3;
pace_ts_load_tracker stream_file(.clk(clk_sys),.reset(core_reset),.download(stream_loading),
 .wr(ioctl_wr && stream_loading),.address(ioctl_addr),.loaded(loaded_stream),.length(stream_length));
wire holding=ioctl_download || !loaded_flash || !loaded_ram || !loaded_state;
wire state_write=ioctl_download && ioctl_wr && ioctl_index==2 && ioctl_addr[1];
wire [31:0] state_data={state_high,ioctl_dout[7:0],ioctl_dout[15:8]};
always @(posedge clk_sys)begin
 previous_download<=ioctl_download;
 if(core_reset)begin
  loaded_flash<=0;loaded_ram<=0;loaded_state<=0;
 end
 else begin
  if(ioctl_download && ioctl_wr)begin
   last_download_index<=ioctl_index;last_download_address<=ioctl_addr;
   if(ioctl_index==2 && !ioctl_addr[1])state_high<={ioctl_dout[7:0],ioctl_dout[15:8]};
  end
  if(previous_download && !ioctl_download)case(last_download_index)
   0:loaded_flash<=last_download_address>=2097150;
   1:loaded_ram<=last_download_address>=16777214;
   2:loaded_state<=last_download_address>=274;
   default:begin end
  endcase
 end
end

wire key_valid,key_pressed;wire [7:0] key_code,last_key;
wire [31:0] key_count;
pace_keyboard_remote keyboard(.clk(clk_sys),.reset(core_reset),.ps2_key(ps2_key),
 .event_valid(key_valid),.event_pressed(key_pressed),.remote_code(key_code),.event_count(key_count));
wire cq,cw,ca,cv,gq,gw,ga,gv,vq,va,vv,tq,ta,tv,dq,da;
wire [28:0] cad,gad,vad,tad,dad;
wire [63:0] cwd,gwd,dwd;wire [7:0] cbe,gbe,dbe;
wire iq,iw,irdy,irq,prdy,device_req,device_ready;wire [31:0] ia,id,ir,pir,dir;wire [1:0] iz;
wire demux_selected=ia[31:12]==20'hb000a;
wire demux_config_ready;
assign device_ready=demux_selected?device_req && demux_config_ready:prdy;
pace_mmio_response mmio_bus(.clk(clk_sys),.reset(core_reset),.hold(holding),.cpu_req(iq),
 .cpu_ready(irdy),.cpu_data(ir),.device_req(device_req),.device_ready(device_ready),.device_data(demux_selected?dir:pir));
wire ts_valid,ts_ready,demux_irq;wire [7:0] ts_data;
wire raw_valid,raw_ready;wire [7:0] raw_data;wire [31:0] tot_rewrites;
wire [31:0] ts_loops,ts_packets,ts_sections,ts_dropped,ts_crc_errors;
wire [31:0] pc,inst,retired,ram_writes,last_ram,mmio_address,mmio_value,mmio_read,mmio_writes,guessed_reads,interrupt_count;
wire [7:0] cpu_halt,model_halt,gpu_error,video_error;
wire mips16;
wire gpu_start,gpu_done,gpu_busy;wire [7:0] gburst;
wire [31:0] gpu_descriptor,osd_root,gpu_count,gpu_last,serial_frames,key_frames,timer_acks,gpu_acks,video_frames,video_underruns;
wire [7:0] halt_code=cpu_halt!=0?cpu_halt:model_halt!=0?model_halt:gpu_error!=0?gpu_error:video_error;
pace_firmware_cpu #(.EXTERNAL_MMIO(1),.CHECKPOINT_PORT(1),.RETIRE_TIMING(1),.ICACHE(1)) cpu(
 .clk(clk_sys),.reset(core_reset),.full_flash_loaded(loaded_flash),.mmio_policy(2'd1),
 .checkpoint_hold(holding),.checkpoint_wr(state_write),.checkpoint_index(ioctl_addr[8:2]),.checkpoint_data(state_data),
 .io_req(iq),.io_we(iw),.io_addr(ia),.io_wdata(id),.io_size(iz),.io_rdata(ir),.io_ready(irdy),.io_irq(irq),
 .mem_req(cq),.mem_we(cw),.mem_addr(cad),.mem_wdata(cwd),.mem_be(cbe),.mem_accept(ca),.mem_rvalid(cv),.mem_rdata(DDRAM_DOUT),
 .pc(pc),.instruction(inst),.retired(retired),.ram_writes(ram_writes),.last_ram_address(last_ram),
 .last_mmio_address(mmio_address),.last_mmio_value(mmio_value),.last_mmio_read(mmio_read),
 .mmio_writes(mmio_writes),.guessed_reads(guessed_reads),.halt_code(cpu_halt),.mips16(mips16),.interrupt_count(interrupt_count));
pace_guide_peripherals devices(.clk(clk_sys),.reset(core_reset),.hold(holding),.retired(retired),
 .io_req(device_req && !demux_selected),.io_we(iw),.io_addr(ia),.io_wdata(id),.io_size(iz),.io_rdata(pir),.io_ready(prdy),.io_irq(irq),
 .key_valid(key_valid),.key_pressed(key_pressed),.key_code(key_code),.gpu_start(gpu_start),
 .gpu_descriptor(gpu_descriptor),.osd_root(osd_root),.gpu_done(gpu_done),.transport_irq(demux_irq),
 .transport_lock(loaded_stream && ts_packets>=3 && !status[4]),.model_halt(model_halt),
 .serial_frames(serial_frames),.key_frames(key_frames),.timer_acks(timer_acks),.gpu_acks(gpu_acks),.last_key(last_key));
pace_guide_blitter gpu(.clk(clk_sys),.reset(core_reset),.hold(holding),.start(gpu_start),.descriptor(gpu_descriptor),
 .done(gpu_done),.busy(gpu_busy),.error(gpu_error),.completions(gpu_count),.last_opcode(gpu_last),
 .mem_req(gq),.mem_we(gw),.mem_addr(gad),.mem_wdata(gwd),.mem_be(gbe),.mem_burst(gburst),
 .mem_accept(ga),.mem_rvalid(gv),.mem_rdata(DDRAM_DOUT));

pace_ts_replay transport(.clk(clk_sys),.reset(core_reset || stream_loading),.hold(holding),
 .enabled(loaded_stream),.length(stream_length),.valid(raw_valid),.ready(raw_ready),.data(raw_data),.loops(ts_loops),
 .mem_req(tq),.mem_addr(tad),.mem_accept(ta),.mem_rvalid(tv),.mem_rdata(DDRAM_DOUT));
// The replayed broadcast's TOT carries today's date/time from the MiSTer RTC.
pace_tot_clock broadcast_clock(.clk(clk_sys),.reset(core_reset || stream_loading),.enable(!status[5]),.rtc(rtc),
 .in_valid(raw_valid),.in_ready(raw_ready),.in_data(raw_data),.out_valid(ts_valid),.out_ready(ts_ready),.out_data(ts_data),.rewritten(tot_rewrites));
pace_section_demux demux(.clk(clk_sys),.reset(core_reset),.stream_reset(stream_loading),.hold(holding),
 .ts_valid(ts_valid),.ts_ready(ts_ready),.ts_data(ts_data),
 .io_req(device_req && demux_selected),.io_we(iw),.io_addr(ia),.io_wdata(id),.io_size(iz),.io_rdata(dir),.irq(demux_irq),.config_ready(demux_config_ready),
 .mem_req(dq),.mem_addr(dad),.mem_wdata(dwd),.mem_be(dbe),.mem_accept(da),
 .packets(ts_packets),.sections(ts_sections),.dropped(ts_dropped),.crc_errors(ts_crc_errors));

wire [9:0] x,y;wire shown,hs,vs,field,ce;
wire [23:0] frame_rgb;wire video_ce,video_de,video_hs,video_vs,video_field;
// Video runs in its own 54 MHz domain: BT.601 13.5 MHz samples, 720 active
// per line, one sample per firmware OSD pixel.
pace_pal576i601 raster(.clk(clk_video),.reset(!pll_locked),.ce_pixel(ce),.x(x),.y(y),.visible(shown),.hs(hs),.vs(vs),.field(field));
pace_guide_video601 scanout(.clk(clk_sys),.reset(core_reset),.hold(holding),.osd_root(osd_root),
 .error(video_error),.frames(video_frames),.underruns(video_underruns),
 .mem_req(vq),.mem_addr(vad),.mem_accept(va),.mem_rvalid(vv),.mem_rdata(DDRAM_DOUT),
 .vclk(clk_video),.x(x),.y(y),.ce(ce),.visible(shown),.hs(hs),.vs(vs),.field(field),
 .out_ce(video_ce),.out_visible(video_de),.out_hs(video_hs),.out_vs(video_vs),.out_field(video_field),.rgb(frame_rgb));

// One outstanding read; it stays owned until its last beat. Only the blitter
// issues multi-beat bursts (source rows), every other master reads 1 beat.
reg [7:0] read_beats=0;
// Video, graphics, section writes, replay reads, CPU. Transport is rate limited.
reg read_pending=0;reg [2:0] read_owner=0;
wire [2:0] owner=vq?3'd2:gq?3'd1:dq?3'd4:tq?3'd3:3'd0;
wire request=vq || gq || dq || tq || cq;
wire write_request=owner==2 || owner==3?1'b0:owner==4?1'b1:owner==1?gw:cw;
wire accepted=request && !holding && !read_pending && !DDRAM_BUSY;
wire load_memory=ioctl_download && (ioctl_index<2 || ioctl_index==3);
wire download_store=load_memory && ioctl_wr && !DDRAM_BUSY && !read_pending && (ioctl_index!=3 || ioctl_addr<1048576);
assign ioctl_wait=load_memory ? (DDRAM_BUSY || read_pending) : 1'b0;
assign ca=accepted && owner==0;assign ga=accepted && owner==1;assign va=accepted && owner==2;
assign cv=DDRAM_DOUT_READY && read_pending && read_owner==0;
assign gv=DDRAM_DOUT_READY && read_pending && read_owner==1;
assign vv=DDRAM_DOUT_READY && read_pending && read_owner==2;
assign ta=accepted && owner==3;assign da=accepted && owner==4;
assign tv=DDRAM_DOUT_READY && read_pending && read_owner==3;
always @(posedge clk_sys)begin
 if(core_reset)read_pending<=0;
 else begin
  if(DDRAM_DOUT_READY && read_pending)begin if(read_beats<=8'd1)read_pending<=0;else read_beats<=read_beats-8'd1;end
  if(accepted && !write_request)begin read_pending<=1;read_owner<=owner;read_beats<=owner==1 ? gburst : 8'd1;end
 end
end
assign DDRAM_ADDR=download_store ?
 (ioctl_index==0 ? 29'h06400000+{8'd0,ioctl_addr[20:3]} : ioctl_index==3?29'h06600000+{9'd0,ioctl_addr[22:3]}:29'h06000000+{5'd0,ioctl_addr[23:3]}) :
 owner==2?vad:owner==1?gad:owner==4?dad:owner==3?tad:cad;
assign DDRAM_DIN=download_store ? ({48'd0,ioctl_dout}<<(ioctl_addr[2:0]*8)) : owner==4?dwd:owner==1?gwd:cwd;
assign DDRAM_BE=download_store ? (8'h03<<ioctl_addr[2:0]) : owner==4?dbe:owner==2 || owner==3?8'hff:owner==1?gbe:cbe;
assign DDRAM_WE=download_store || (accepted && write_request);
assign DDRAM_BURSTCNT=(!download_store && owner==1 && !write_request) ? gburst : 8'd1;
assign DDRAM_RD=accepted && !write_request;

wire [7:0] monitor_r,monitor_g,monitor_b;
// Diagnostic monitor text reads core-domain counters asynchronously; a value
// may tear for one frame, which is acceptable for this display-only screen.
pace_boot_monitor monitor(.clk(clk_video),.x(x),.y(y),.pc(pc),.instruction(inst),.retired(retired),
 .ram_writes(ram_writes),.last_ram_address(last_ram),.last_mmio_address(mmio_address),.last_mmio_value(mmio_value),
 .last_mmio_read(mmio_read),.mmio_writes(mmio_writes),.interrupt_count(interrupt_count),
 .guessed_reads(key_count),.halt_code(halt_code),.mips16(mips16),.full_flash_loaded(loaded_flash),
 .mmio_policy(2'd1),.r(monitor_r),.g(monitor_g),.b(monitor_b));
wire diagnostics=status[3] || holding || halt_code!=0;
assign CLK_VIDEO=clk_video;
assign CE_PIXEL=diagnostics?ce:video_ce;
assign VGA_HS=diagnostics?hs:video_hs;assign VGA_VS=diagnostics?vs:video_vs;
assign VGA_DE=diagnostics?shown:video_de;assign VGA_F1=diagnostics?field:video_field;
assign VGA_R=diagnostics?(shown?monitor_r:8'd0):(video_de?frame_rgb[23:16]:8'd0);
assign VGA_G=diagnostics?(shown?monitor_g:8'd0):(video_de?frame_rgb[15:8]:8'd0);
assign VGA_B=diagnostics?(shown?monitor_b:8'd0):(video_de?frame_rgb[7:0]:8'd0);
assign LED_USER=halt_code!=0?field:retired[21];
pace_debug_uart telemetry(.clk(clk_sys),.reset(!pll_locked),.tx(UART_TXD),
 .pc(pc),.instruction(inst),.retired(retired),.ram_writes(ram_writes),
 .mmio_address({gpu_count[15:0],ts_sections[15:0]}),.mmio_value({key_count[15:0],key_frames[15:0]}),
 .mmio_read({8'd0,last_key,video_underruns[15:0]}),.interrupt_count(interrupt_count),
 .guessed_reads(ts_packets),.mmio_policy(2'd1),.halt_code(halt_code),.mips16(mips16),.full_flash_loaded(loaded_flash));
endmodule

