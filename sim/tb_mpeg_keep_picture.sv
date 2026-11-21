`timescale 1ns/1ps
// Firmware ends its memory-ES input after capturing the image; the displayed
// picture must survive that stop and FIFO flush, then release for a new source.
module tb_mpeg_keep_picture;
 tb_mpeg_video b();
 reg [1:0] frame;
 integer count;
 initial begin
  wait(!b.reset);wait(b.capture_valid);
  @(negedge b.clk_sys);frame=b.capture_frame;b.keep_picture_in=1;b.stream_enable=0;
  repeat(16)@(negedge b.clk_sys);
  b.enable_in=0;b.flush_in=1;
  repeat(256)@(negedge b.clk_sys);b.flush_in=0;
  repeat(1000000)@(negedge b.clk_sys);
  if(!b.video_live || !b.capture_valid || b.capture_frame!=frame || !b.dut.sync_rst)
   $fatal(1,"Captured picture lost on input stop: live%b valid%b frame%0d reset%b",b.video_live,b.capture_valid,b.capture_frame,b.dut.sync_rst);
  $display("PASS captured picture retained after input stop and FIFO flush");
  @(negedge b.clk_sys);b.keep_picture_in=0;b.flush_in=1;
  repeat(256)@(negedge b.clk_sys);
  if(b.capture_valid)$fatal(1,"Picture validity survived a real decoder reset");
  b.flush_in=0;b.enable_in=1;b.position=0;b.stream_enable=1;
  count=0;
  while(!b.capture_valid && count<7500000)begin @(negedge b.clk_sys);count=count+1;end
  if(!b.capture_valid)$fatal(1,"Fresh picture not decoded after leaving retained still");
  $display("PASS retained still -> decoder reset -> fresh decoded picture");$finish;
 end
 initial begin #250000000;$fatal(1,"Keep-picture test timeout");end
endmodule
