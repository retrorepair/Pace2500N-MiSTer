`timescale 1ns/1ps
// A/V path bench: transport stream -> PES extraction (firmware-style PIDs) ->
// MPEG-2 video decoder + MP2 audio decoder, with the OSD raster locked to the
// decoder and the mixed output captured as frames. Checks raster alignment.
//   +TS=file.hex +BYTES=n +FRAMES=n +OUT=prefix
module tb_av;
 reg clk_sys=0,clk_dec=0,clk_mem=0,clk_video=0,clk_dot=0,reset=1;
 always #10 clk_sys=~clk_sys;      // 50 MHz
 always #6.25 clk_dec=~clk_dec;    // 80 MHz
 always #5.5 clk_mem=~clk_mem;     // ~90.9 MHz
 always #9.25 clk_video=~clk_video;// ~54 MHz
 always @(posedge clk_video)clk_dot<=~clk_dot; // 27 MHz, phase-aligned
 integer ts_bytes=0,max_frames=4,frames=0;
 string ts_file="sim/av_ts.hex",out_prefix="sim/av_frame";
 reg [7:0] ts[0:24*1024*1024-1];
 integer position=0,pace=0;
 reg ts_strobe=0;reg [7:0] ts_data=0;
 wire [7:0] v_data,a_data;wire v_valid,v_ready,a_valid;wire a_full;
 wire [31:0] v_bytes,a_bytes;wire [15:0] v_drop,a_drop;
 reg [31:0] v_taken=0;
 // Stand-in for real-time pacing: hold the stream while the video FIFO is filling.
 wire v_fifo_room=(v_bytes-v_taken)<2000;
 always @(posedge clk_sys)begin
  ts_strobe<=0;
  if(v_valid && v_ready)v_taken<=v_taken+1;
  if(!reset && position<ts_bytes)begin
   if(pace==0)begin
    if(v_fifo_room)begin ts_strobe<=1;ts_data<=ts[position];position<=position+1;pace<=7;end
   end else pace<=pace-1;
  end
 end
 pace_av_pes pes(.clk(clk_sys),.reset(reset),.ts_strobe(ts_strobe),.ts_data(ts_data),
  .video_pid(13'h200),.audio_pid(13'h102),.video_on(1'b1),.audio_on(1'b1),
  .video_data(v_data),.video_valid(v_valid),.video_ready(v_ready),
  .audio_data(a_data),.audio_valid(a_valid),.audio_ready(!a_full),
  .video_bytes(v_bytes),.audio_bytes(a_bytes),.video_dropped(v_drop),.audio_dropped(a_drop));
 // ---- video decoder + DDR model
 wire [28:0] ddr_addr;wire [7:0] ddr_burstcnt,ddr_be;wire ddr_read,ddr_write;wire [63:0] ddr_wdata;
 reg [63:0] ddr_rdata=0;reg ddr_rvalid=0;wire ddr_waitrequest;
 wire [7:0] r,g,b;wire pixel_en,dhs,dvs;wire [11:0] h_pos,v_pos;
 wire video_live,busy;wire [15:0] pictures,pickups,frames_late;wire [7:0] vbuf_fill;wire [13:0] hsize,vsize;
 pace_mpeg_video video(.clk_sys(clk_sys),.clk_dec(clk_dec),.clk_mem(clk_mem),.clk_dot(clk_dot),.reset(reset),.enable(1'b1),
  .es_data(v_data),.es_valid(v_valid),.es_ready(v_ready),
  .ddr_addr(ddr_addr),.ddr_burstcnt(ddr_burstcnt),.ddr_read(ddr_read),.ddr_write(ddr_write),.ddr_wdata(ddr_wdata),.ddr_be(ddr_be),
  .ddr_rdata(ddr_rdata),.ddr_rvalid(ddr_rvalid),.ddr_waitrequest(ddr_waitrequest),
  .r(r),.g(g),.b(b),.pixel_en(pixel_en),.hs(dhs),.vs(dvs),.h_pos(h_pos),.v_pos(v_pos),
  .video_live(video_live),.busy(busy),.pictures(pictures),.pickups(pickups),.frames_late(frames_late),.vbuf_fill(vbuf_fill),
  .horizontal_size(hsize),.vertical_size(vsize));
 reg [63:0] mem[0:4*1024*1024-1];
 reg [21:0] rd_word=0;reg [8:0] rd_left=0;reg [3:0] rd_wait=0;integer lane;
 assign ddr_waitrequest=rd_left!=0;
 always @(posedge clk_mem)begin
  ddr_rvalid<=0;
  if(ddr_write && !ddr_waitrequest)for(lane=0;lane<8;lane=lane+1)if(ddr_be[lane])mem[ddr_addr[21:0]][lane*8+:8]<=ddr_wdata[lane*8+:8];
  if(ddr_read && !ddr_waitrequest)begin rd_word<=ddr_addr[21:0];rd_left<={1'b0,ddr_burstcnt};rd_wait<=6;end
  else if(rd_left!=0)begin
   if(rd_wait!=0)rd_wait<=rd_wait-1;
   else begin ddr_rdata<=mem[rd_word];ddr_rvalid<=1;rd_word<=rd_word+1;rd_left<=rd_left-1;end
  end
 end
 // ---- OSD raster locked to the decoder; the OSD itself is fully transparent here.
 wire sync,sync_field,ce,shown,hs,vs,field;wire [9:0] x,y;
 pace_pal576i601 raster(.clk(clk_video),.reset(reset),.sync(sync),.sync_field(sync_field),
  .ce_pixel(ce),.x(x),.y(y),.visible(shown),.hs(hs),.vs(vs),.field(field));
 // the three pipeline stages of the OSD scan-out
 reg [22:0] p1=0,p2=0,p3=0; // {ce,visible,field,x,y}
 always @(posedge clk_video)begin p1<={ce,shown,field,x,y};p2<=p1;p3<=p2;end
 wire out_ce=p3[22],out_de=p3[21],out_field=p3[20];wire [9:0] out_x=p3[19:10],out_y=p3[9:0];
 wire [23:0] rgb;wire dbg_en;wire [23:0] dbg_rgb;
 pace_video_mix mix(.clk_video(clk_video),.dec_r(r),.dec_g(g),.dec_b(b),.dec_en(pixel_en),.dec_vs(dvs),.dec_v(v_pos),
  .show_video(1'b1),.sync(sync),.sync_field(sync_field),.osd_rgb(24'hff00ff),.osd_key(1'b1),.osd_de(out_de),.rgb(rgb),
  .dbg_en(dbg_en),.dbg_rgb(dbg_rgb));
 // ---- MP2 audio
 wire signed [15:0] audio_l,audio_r;wire aud_valid,mp2_synced,mp2_err;wire [1:0] fs;
 reg [31:0] aud_acc=0;reg aud_ce=0;
 always @(posedge clk_sys)begin
  aud_ce<=0;
  if(aud_acc+32'd48000>=32'd50000000)begin aud_acc<=aud_acc+32'd48000-32'd50000000;aud_ce<=1;end
  else aud_acc<=aud_acc+32'd48000;
 end
 mp2_decode mp2(.clk(clk_sys),.rst(reset),.wr_en(a_valid && !a_full),.wr_data(a_data),.full(a_full),
  .aud_ce(aud_ce),.audio_l(audio_l),.audio_r(audio_r),.aud_valid(aud_valid),.synced(mp2_synced),.err_unsupported(mp2_err),
  .fs_o(fs),.dbg_s_nz(),.dbg_pcm_nz(),.cp_step(1'b0),.cp_q());
 integer pcm_fd,pcm_pairs=0;
 always @(posedge clk_sys)if(aud_valid)begin
  $fwrite(pcm_fd,"%c%c%c%c",audio_l[7:0],audio_l[15:8],audio_r[7:0],audio_r[15:8]);pcm_pairs<=pcm_pairs+1;
 end
 // ---- capture + alignment statistics
 reg [23:0] image[0:720*576-1];
 integer syncs=0,mis_edge=0,mis_en=0,samples=0,fd,px,py,tearing=0,first_x=-1;
 reg field_d=0;string name;
 reg [23:0] prev_dbg=0;reg prev_ce=0,prev_dbg_en=0;
 always @(posedge clk_video)begin
  prev_dbg<=dbg_rgb;prev_ce<=out_ce;prev_dbg_en<=dbg_en;
  if(sync)syncs<=syncs+1;
  // where (in OSD raster samples) does each decoder line start?
  if(dbg_en && !prev_dbg_en && video_live && first_x<0)first_x<=out_de ? out_x : -2;
  if(out_de && video_live)begin
   if(!dbg_en)mis_en<=mis_en+1;                              // OSD raster active, decoder not
   if(!prev_ce && prev_dbg_en && dbg_en && dbg_rgb!==prev_dbg)tearing<=tearing+1; // changed mid-sample
   if(out_ce)begin image[out_y*720+out_x]<=rgb;samples<=samples+1;end
  end
  if(!out_de && dbg_en && video_live)mis_edge<=mis_edge+1;      // decoder active outside the OSD raster
  field_d<=out_field;
  if(field_d && !out_field && video_live)begin
   $display("FRAME %0d t=%0t samples %0d syncs %0d osd-only %0d dec-only %0d tearing %0d first_x %0d pictures %0d pickups %0d late %0d vbuf %0d v/a bytes %0d/%0d drops %0d/%0d mp2 sync %b err %b pcm %0d",
    frames,$time,samples,syncs,mis_en,mis_edge,tearing,first_x,pictures,pickups,frames_late,vbuf_fill,v_bytes,a_bytes,v_drop,a_drop,mp2_synced,mp2_err,pcm_pairs);
   name=$sformatf("%s_%0d.ppm",out_prefix,frames);
   fd=$fopen(name,"wb");$fwrite(fd,"P6\n720 576\n255\n");
   for(py=0;py<576;py=py+1)for(px=0;px<720;px=px+1)$fwrite(fd,"%c%c%c",image[py*720+px][23:16],image[py*720+px][15:8],image[py*720+px][7:0]);
   $fclose(fd);
   samples<=0;mis_en<=0;mis_edge<=0;tearing<=0;first_x<=-1;frames<=frames+1;
   if(frames+1>=max_frames)begin $fclose(pcm_fd);$display("DONE");$finish;end
  end
 end
 initial begin
  if($value$plusargs("TS=%s",ts_file))begin end
  if($value$plusargs("OUT=%s",out_prefix))begin end
  if($value$plusargs("FRAMES=%d",max_frames))begin end
  if(!$value$plusargs("BYTES=%d",ts_bytes))ts_bytes=8*1024*1024;
  $readmemh(ts_file,ts);
  pcm_fd=$fopen({out_prefix,".pcm"},"wb");
  repeat(40)@(posedge clk_sys);reset=0;
  #600000000;
  $display("TIMEOUT frames %0d pictures %0d pickups %0d pos %0d v/a %0d/%0d",frames,pictures,pickups,position,v_bytes,a_bytes);$fclose(pcm_fd);$finish;
 end
endmodule
