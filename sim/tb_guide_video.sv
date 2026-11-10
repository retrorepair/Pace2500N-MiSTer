`timescale 1ns/1ps
module tb_guide_video;
 reg clk=0,reset=1;always #10 clk=~clk;
 reg[63:0] ram[0:2097151];
 wire[9:0] x,y;wire ce,de,hs,vs,field;
 wire oce,ode,oh,ov,ofield;wire[23:0] rgb;
 wire req;wire[28:0] addr;wire[7:0] error;wire[31:0] frames,underruns;
 integer cycles=0,wait_count=0,column=0,checked=0,bad=0;
 reg response=0;reg[63:0] data=0,saved_data=0;
 wire accept=req && wait_count==0 && cycles%4==1;
 pace_pal576i raster(clk,reset,ce,x,y,de,hs,vs,field);
 pace_guide_video video(.clk(clk),.reset(reset),.hold(1'b0),.osd_root(32'h01583fe8),
  .x(x),.y(y),.ce(ce),.visible(de),.hs(hs),.vs(vs),.field(field),
  .out_ce(oce),.out_visible(ode),.out_hs(oh),.out_vs(ov),.out_field(ofield),.rgb(rgb),
  .error(error),.frames(frames),.underruns(underruns),.mem_req(req),.mem_addr(addr),
  .mem_accept(accept),.mem_rvalid(response),.mem_rdata(data));
 function automatic integer byte_at(input integer at);
  byte_at=(ram[at>>3]>>((at&7)*8))&255;
 endfunction
 function automatic integer clamp(input integer v);clamp=v<0?0:v>255?255:v;endfunction
 integer base,pixel,entry,yy,cb,cr,er,eg,eb;
 always @(posedge clk)begin
  cycles<=cycles+1;response<=0;
  if(wait_count>0)begin
   wait_count<=wait_count-1;
   if(wait_count==1)begin response<=1;data<=saved_data;end
  end
  if(accept)begin
   if(addr<29'h06000000 || addr>=29'h06200000)$fatal(1,"scanout address %h",addr);
   saved_data<=ram[addr-29'h06000000];wait_count<=12;
  end
 end
 always @(negedge clk)begin
  if(!ode)column=0;
  else if(oce)begin
   if(frames>=3)begin
    base=y[0]?32'h5b6a58:32'h584048;
    pixel=byte_at(base+(y>>1)*720+column+column/8);
    entry=byte_at(32'h5e9468+pixel*2)*256+byte_at(32'h5e9468+pixel*2+1);
    yy=((entry>>8)&63)*4;cb=((entry>>4)&15)*16-128;cr=(entry&15)*16-128;
    er=clamp($rtoi(1.164*(yy-16)+1.596*cr));
    eg=clamp($rtoi(1.164*(yy-16)-0.392*cb-0.813*cr));
    eb=clamp($rtoi(1.164*(yy-16)+2.017*cb));
    if($signed({1'b0,rgb[23:16]})<er-2 || $signed({1'b0,rgb[23:16]})>er+2 ||
       $signed({1'b0,rgb[15:8]})<eg-2 || $signed({1'b0,rgb[15:8]})>eg+2 ||
       $signed({1'b0,rgb[7:0]})<eb-2 || $signed({1'b0,rgb[7:0]})>eb+2)begin
     if(bad<5)$display("mismatch x%d y%d got%h expected%d,%d,%d",column,y,rgb,er,eg,eb);
     bad=bad+1;
    end
    checked=checked+1;
   end
   column=column+1;
  end
 end
 reg[31:0] prior;
 initial begin
  $readmemh("re/fpga_guide_checkpoint/ram64.hex",ram);
  repeat(4)@(negedge clk);reset=0;
  wait(frames==3);prior=underruns;
  wait(frames==6);@(negedge clk);
  if(error!=0 || underruns!=prior || bad!=0 || checked<500000)
   $fatal(1,"video errors %h underruns%d->%d bad%d checked%d",error,prior,underruns,bad,checked);
  $display("PASS: actual Guide RAM pixels/CLUT across PAL fields, delayed DDR, no new underruns; checked %d",checked);$finish;
 end
 initial begin #200000000;$fatal(1,"video timeout");end
endmodule
