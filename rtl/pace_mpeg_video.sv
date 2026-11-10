// SPDX-License-Identifier: GPL-3.0-only
// MPEG-2 video decoder for the Pace 2500N core: the mpeg2fpga decoder
// (Koen De Vleeschauwer) as carried and extended by MiSTer_DVD (rtl/mpeg2),
// wired the way MiSTer_DVD's emu.sv wires it, minus everything DVD-specific.
//
//  - Elementary-stream bytes arrive in clk_sys (from the transport demux's
//    video PID) and cross to the decoder clock through vidfeed_cdc.
//  - The decoder owns its own frame/bitstream memory through mem_shim_burst
//    on a dedicated DDR3 port (window relocated to HPS 0x38000000, see
//    rtl/mpeg2/dvd/mem_shim_burst.sv); the firmware CPU's memory is untouched.
//  - The raster is programmed once after reset as PAL 576i fields (864 x 312/313
//    at a 27 MHz dot clock with pixel repetition = 13.5 MHz samples), the
//    values MiSTer_DVD uses for its native 576i output.
//  - Display scheduling runs free (no PTS): pictures are shown as decoded at
//    the raster rate. A/V sync against PCR/PTS is not modelled yet.
module pace_mpeg_video(
 input wire clk_sys,clk_dec,clk_mem,clk_dot,
 input wire reset,                 // asynchronous, active high
 input wire enable,                // clk_sys level: decode and show video
 // elementary stream, clk_sys
 input wire [7:0] es_data,input wire es_valid,output wire es_ready,
 // DDR3 (Avalon-MM, clk_mem)
 output wire [28:0] ddr_addr,output wire [7:0] ddr_burstcnt,output wire ddr_read,ddr_write,
 output wire [63:0] ddr_wdata,output wire [7:0] ddr_be,
 input wire [63:0] ddr_rdata,input wire ddr_rvalid,ddr_waitrequest,
 // video, clk_dot
 output wire [7:0] r,g,b,output wire pixel_en,hs,vs,output wire [11:0] h_pos,v_pos,
 // status, clk_dec
 output wire video_live,busy,output wire [15:0] pictures,pickups,frames_late,output wire [7:0] vbuf_fill,
 output wire [13:0] horizontal_size,vertical_size
);
 wire reset_n=!reset;
 // ---- stream feed
 wire [7:0] dec_data;wire dec_mark,dec_valid;
 vidfeed_cdc feed(.rst_n(reset_n),.wr_clk(clk_sys),.wr_data({1'b0,es_data}),.wr_valid(es_valid),.wr_ready(es_ready),
  .rd_clk(clk_dec),.rd_data({dec_mark,dec_data}),.rd_valid(dec_valid),.rd_ready(!busy));
 // ---- 90 kHz tick: clk_dot/300, crossed to clk_dec by a toggle.
 reg [8:0] stc_div=0;reg stc_tog=0;
 always @(posedge clk_dot or negedge reset_n)
  if(!reset_n)begin stc_div<=0;stc_tog<=0;end
  else if(stc_div==9'd299)begin stc_div<=0;stc_tog<=~stc_tog;end
  else stc_div<=stc_div+9'd1;
 reg stc_t1=0,stc_t2=0,stc_t3=0;
 always @(posedge clk_dec or negedge reset_n)
  if(!reset_n)begin stc_t1<=0;stc_t2<=0;stc_t3<=0;end
  else begin stc_t1<=stc_tog;stc_t2<=stc_t1;stc_t3<=stc_t2;end
 wire stc_tick=stc_t2^stc_t3;
 // ---- enable -> decoder flush (held while video is off), clk_dec
 reg en1=0,en2=0;
 always @(posedge clk_dec)begin en1<=enable;en2<=en1;end
 // ---- raster programming walk (PAL 576i), after the decoder's own reset.
 localparam [3:0] REG_WR_HOR=4'h1,REG_WR_HOR_SYNC=4'h2,REG_WR_VER=4'h3,REG_WR_VER_SYNC=4'h4,
                  REG_WR_VID_MODE=4'h5,REG_WR_TRICK=4'hb;
 wire sync_rst;
 reg [2:0] ready_count=0,step=0;reg walking=0,walked=0;
 reg [3:0] wr_addr;reg [31:0] wr_data;
 always @* case(step)
  3'd0:begin wr_addr=REG_WR_HOR;wr_data={4'b0,12'd720,4'b0,12'd863};end        // 864 dots per line
  3'd1:begin wr_addr=REG_WR_HOR_SYNC;wr_data={4'b0,12'd732,4'b0,12'd795};end
  3'd2:begin wr_addr=REG_WR_VER;wr_data={4'b0,12'd576,4'b0,12'd311};end        // 312/313 lines per field
  3'd3:begin wr_addr=REG_WR_VER_SYNC;wr_data={4'b0,12'd292,4'b0,12'd295};end
  3'd4:begin wr_addr=REG_WR_VID_MODE;wr_data={4'b0,12'd432,13'b0,3'b011};end   // half-line 432, pixrep, interlaced
  default:begin wr_addr=REG_WR_TRICK;wr_data={21'b0,1'b0,5'b00000,1'b1,3'b000,1'b0};end // fields, persistence
 endcase
 always @(posedge clk_dec)begin
  if(!reset_n || !sync_rst)ready_count<=0;
  else if(ready_count!=3'd7)ready_count<=ready_count+3'd1;
  if(!reset_n)begin walking<=0;walked<=0;step<=0;end
  else if(walking)begin if(step==3'd5)walking<=0;step<=step+3'd1;end
  else if(ready_count==3'd7 && !walked)begin walked<=1;walking<=1;step<=0;end
 end
 // ---- decoder
 wire [1:0] mem_cmd;wire [21:0] mem_addr;wire [63:0] mem_dta,res_dta;wire mem_en,mem_valid,res_en,res_almost_full;
 mpeg2video decoder(
  .clk(clk_dec),.mem_clk(clk_mem),.dot_clk(clk_dot),.dot_ce(1'b1),.rst(reset_n),
  .stream_data(dec_data),.stream_valid(dec_valid),.stream_mark(1'b0),.pts_in(33'd0),.pts_in_valid(1'b0),
  .stc_tick(stc_tick),.sched_en(1'b0),.half_scan(16'd900),
  .stc(),.stc_anchored(),.disp_anchored(),.anchor_req(),.anchor_disc(),.cc_credit_valid(),.cc_credit(),
  .anchor_delta(),.disp_lag(),.disp_lag_valid(),.sched_dbg_flags(),.sched_dbg_dur(),
  .reg_addr(walking ? wr_addr : 4'd0),.reg_wr_en(walking),.reg_dta_in(wr_data),.reg_rd_en(1'b0),.reg_dta_out(),
  .busy(busy),.error(),.interrupt(),.watchdog_rst(),
  .r(r),.g(g),.b(b),.y(),.u(),.v(),.pixel_en(pixel_en),.h_sync(hs),.v_sync(vs),.c_sync(),.h_pos(h_pos),.v_pos(v_pos),
  .mem_req_rd_cmd(mem_cmd),.mem_req_rd_addr(mem_addr),.mem_req_rd_dta(mem_dta),.mem_req_rd_en(mem_en),.mem_req_rd_valid(mem_valid),
  .mem_res_wr_dta(res_dta),.mem_res_wr_en(res_en),.mem_res_wr_almost_full(res_almost_full),
  .testpoint_dip(4'b0),.testpoint_dip_en(1'b0),.testpoint(),
  .init_cnt_out(),.sync_rst_out(sync_rst),.vbw_almost_full_out(),
  .dbg_lines_displayed(),.dbg_first_vpos(),.dbg_last_vpos(),
  .dbg_prof0(),.dbg_prof1(),.dbg_prof2(),.dbg_prof3(),.dbg_pic_max(),.dbg_pic_n(pictures),.dbg_pic_over(),
  .dbg_fb_heals(),.dbg_strict_waits(),.cc_pair_valid(),.cc_pair(),.cc_pair_field(),
  .vertical_size_out(vertical_size),.horizontal_size_out(horizontal_size),.aspect_ratio_out(),
  .ref_prefetch_en(1'b1),.frame_drop_en(1'b1),
  .dbg_frames_late(frames_late),.dbg_frames_dropped(),.dbg_pickups(pickups),.dbg_drop_costs(),.dbg_vbuf_fill(vbuf_fill),
  .video_live(video_live),.pickup_hold(1'b0),.pause(1'b0),.step_req(1'b0),.freeze_wd(1'b0),
  .vbuf_flush(!en2),.soft_flush(!en2),
  .disp_vscale_mode(2'd0),.disp_vscale_en(1'b0),.disp_hcrop_en(1'b0),.disp_hfill_en(1'b0),
  .film24(1'b0),.film_det_ntsc(),.film_det_pal(),.blend_en(1'b0),.blend_act(),.bob_en(1'b0),.bob_act());
 // ---- frame/bitstream memory
 mem_shim_burst #(.NSETS(64)) memory(
  .clk(clk_mem),.rst_n(reset_n),.hard_rst_n(reset_n),.cwf_en(1'b1),.dual_en(1'b1),
  .mem_req_rd_cmd(mem_cmd),.mem_req_rd_addr(mem_addr),.mem_req_rd_dta(mem_dta),.mem_req_rd_en(mem_en),.mem_req_rd_valid(mem_valid),
  .mem_res_wr_dta(res_dta),.mem_res_wr_en(res_en),.mem_res_wr_almost_full(res_almost_full),
  .ddr3_addr(ddr_addr),.ddr3_burstcnt(ddr_burstcnt),.ddr3_read(ddr_read),.ddr3_write(ddr_write),
  .ddr3_writedata(ddr_wdata),.ddr3_byteenable(ddr_be),
  .ddr3_readdata(ddr_rdata),.ddr3_readdatavalid(ddr_rvalid),.ddr3_waitrequest(ddr_waitrequest),
  .debug_state(),.debug_saved_cmd(),.debug_sdram_busy(),.debug_sdram_ack(),
  .debug_rd_count(),.debug_wr_count(),.debug_rsp_count(),.debug_read_pend_cycles(),.debug_cache_missrate());
endmodule
