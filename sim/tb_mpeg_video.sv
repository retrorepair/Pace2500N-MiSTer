`timescale 1ns/1ps
// Decoder bring-up bench: feeds a video elementary stream into pace_mpeg_video,
// models the f2sdram DDR3 port, and writes every displayed field as a PPM.
//   +ES=file.hex ($readmemh bytes)  +BYTES=n  +FIELDS=n  +OUT=prefix
module tb_mpeg_video;
 reg clk_sys=0,clk_dec=0,clk_mem=0,clk_dot=0,reset=1;
 always #10 clk_sys=~clk_sys;      // 50 MHz
 always #6.25 clk_dec=~clk_dec;    // 80 MHz
 always #5.5 clk_mem=~clk_mem;     // ~90.9 MHz
 always #18.5 clk_dot=~clk_dot;    // ~27 MHz
 integer es_bytes=0,max_fields=6,fields=0;
 string es_file="sim/video_es.hex",out_prefix="sim/mpeg_field";
 reg [7:0] es[0:16*1024*1024-1];
 integer position=0;
 wire es_ready;wire es_valid=!reset && position<es_bytes;
 wire [28:0] ddr_addr;wire [7:0] ddr_burstcnt,ddr_be;wire ddr_read,ddr_write;wire [63:0] ddr_wdata;
 reg [63:0] ddr_rdata=0;reg ddr_rvalid=0;wire ddr_waitrequest;
 wire [7:0] r,g,b;wire pixel_en,hs,vs;wire [11:0] h_pos,v_pos;
 wire video_live,busy;wire [15:0] pictures,pickups,frames_late;wire [7:0] vbuf_fill;wire [13:0] hsize,vsize;
 pace_mpeg_video dut(.clk_sys(clk_sys),.clk_dec(clk_dec),.clk_mem(clk_mem),.clk_dot(clk_dot),.reset(reset),.enable(1'b1),
  .es_data(es[position]),.es_valid(es_valid),.es_ready(es_ready),
  .ddr_addr(ddr_addr),.ddr_burstcnt(ddr_burstcnt),.ddr_read(ddr_read),.ddr_write(ddr_write),.ddr_wdata(ddr_wdata),.ddr_be(ddr_be),
  .ddr_rdata(ddr_rdata),.ddr_rvalid(ddr_rvalid),.ddr_waitrequest(ddr_waitrequest),
  .r(r),.g(g),.b(b),.pixel_en(pixel_en),.hs(hs),.vs(vs),.h_pos(h_pos),.v_pos(v_pos),
  .video_live(video_live),.busy(busy),.pictures(pictures),.pickups(pickups),.frames_late(frames_late),.vbuf_fill(vbuf_fill),
  .horizontal_size(hsize),.vertical_size(vsize));
 always @(posedge clk_sys)if(es_valid && es_ready)position<=position+1;
 // ---- DDR3 model: 32 MB window at word address 0x07000000, burst reads, 6-cycle latency.
 reg [63:0] mem[0:4*1024*1024-1];
 reg [21:0] rd_word=0;reg [8:0] rd_left=0;reg [3:0] rd_wait=0;
 integer ddr_reads=0,ddr_writes=0,bad_addr=0,lane;
 assign ddr_waitrequest=rd_left!=0;
 always @(posedge clk_mem)begin
  ddr_rvalid<=0;
  if(ddr_write && !ddr_waitrequest)begin
   if(ddr_addr[28:22]!=7'b0011100)bad_addr<=bad_addr+1;
   for(lane=0;lane<8;lane=lane+1)if(ddr_be[lane])mem[ddr_addr[21:0]][lane*8+:8]<=ddr_wdata[lane*8+:8];
   ddr_writes<=ddr_writes+1;
  end
  if(ddr_read && !ddr_waitrequest)begin
   if(ddr_addr[28:22]!=7'b0011100)bad_addr<=bad_addr+1;
   rd_word<=ddr_addr[21:0];rd_left<={1'b0,ddr_burstcnt};rd_wait<=6;ddr_reads<=ddr_reads+1;
  end else if(rd_left!=0)begin
   if(rd_wait!=0)rd_wait<=rd_wait-1;
   else begin ddr_rdata<=mem[rd_word];ddr_rvalid<=1;rd_word<=rd_word+1;rd_left<=rd_left-1;end
  end
 end
 // ---- field capture
 reg [23:0] image[0:720*640-1];
 integer max_x=0,max_y=0,min_y=4095,pixels=0,fd,x,y;
 reg vs_d=0,pe_d=0;reg [11:0] first_h=0,first_v=0;integer since_vs=0,first_after_vs=-1,line_first=-1,since_hs=0;reg hs_d=0;
 string name;
 always @(posedge clk_dot)begin
  vs_d<=vs;hs_d<=hs;since_vs<=since_vs+1;since_hs<=since_hs+1;
  if(hs && !hs_d)since_hs<=0;
  if(pixel_en)begin
   if(h_pos<720 && v_pos<640)image[v_pos*720+h_pos]<={r,g,b};
   if(pixels==0)begin first_h<=h_pos;first_v<=v_pos;first_after_vs<=since_vs;line_first<=since_hs;end
   if(h_pos>max_x)max_x<=h_pos;if(v_pos>max_y)max_y<=v_pos;if(v_pos<min_y)min_y<=v_pos;
   pixels<=pixels+1;
  end
  if(vs && !vs_d)begin
   since_vs<=0;
   if(pixels!=0)begin
    $display("FIELD %0d t=%0t pixels %0d x<=%0d y %0d..%0d first (%0d,%0d) %0d dots after vs, %0d after hs; pictures %0d pickups %0d vbuf %0d live %b size %0dx%0d ddr r/w %0d/%0d bad %0d",
     fields,$time,pixels,max_x,min_y,max_y,first_h,first_v,first_after_vs,line_first,pictures,pickups,vbuf_fill,video_live,hsize,vsize,ddr_reads,ddr_writes,bad_addr);
    name=$sformatf("%s_%0d.ppm",out_prefix,fields);
    fd=$fopen(name,"wb");$fwrite(fd,"P6\n720 %0d\n255\n",max_y+1);
    for(y=0;y<=max_y;y=y+1)for(x=0;x<720;x=x+1)$fwrite(fd,"%c%c%c",image[y*720+x][23:16],image[y*720+x][15:8],image[y*720+x][7:0]);
    $fclose(fd);
    fields<=fields+1;
    if(fields+1>=max_fields)begin $display("DONE");$finish;end
   end else $display("VSYNC t=%0t no pixels; pictures %0d pickups %0d vbuf %0d busy %b pos %0d ddr r/w %0d/%0d",$time,pictures,pickups,vbuf_fill,busy,position,ddr_reads,ddr_writes);
   pixels<=0;max_x<=0;max_y<=0;min_y<=4095;
  end
 end
 initial begin
  if($value$plusargs("ES=%s",es_file))begin end
  if($value$plusargs("OUT=%s",out_prefix))begin end
  if($value$plusargs("FIELDS=%d",max_fields))begin end
  if(!$value$plusargs("BYTES=%d",es_bytes))es_bytes=4*1024*1024;
  $readmemh(es_file,es);
  repeat(40)@(posedge clk_sys);reset=0;
  #400000000; // 400 ms
  $display("TIMEOUT pictures %0d pickups %0d pos %0d",pictures,pickups,position);$finish;
 end
endmodule
