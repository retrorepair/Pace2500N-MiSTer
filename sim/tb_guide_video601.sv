`timescale 1ns/1ps
// BT.601 scanout check: every one of the 720 guest pixels per line must reach
// the output exactly once, with the CLUT colour, across interlaced fields,
// with a 50 MHz core/DDR clock and an asynchronous 54 MHz video clock.
module tb_guide_video601;
 reg clk=0,vclk=0,reset=1;
 always #10 clk=~clk;           // 50 MHz core
 always #9.259 vclk=~vclk;      // 54 MHz video
 reg[63:0] ram[0:2097151];
 wire[9:0] x,y;wire ce,de,hs,vs,field;
 wire oce,ode,oh,ov,ofield;wire[23:0] rgb;
 wire req;wire[28:0] addr;wire[7:0] error;wire[31:0] frames,underruns;
 integer cycles=0,wait_count=0,column=0,checked=0,bad=0,lines=0,short_lines=0;
 integer active_columns=0,hs_low=0,line_samples=0,last_line_samples=0;
 reg response=0;reg[63:0] data=0,saved_data=0;reg last_ode=0,last_oh=1;
 wire accept=req && wait_count==0 && cycles%4==1;
 pace_pal576i601 raster(vclk,reset,ce,x,y,de,hs,vs,field);
 pace_guide_video601 video(.clk(clk),.reset(reset),.hold(1'b0),.osd_root(32'h01583fe8),
  .error(error),.frames(frames),.underruns(underruns),.mem_req(req),.mem_addr(addr),
  .mem_accept(accept),.mem_rvalid(response),.mem_rdata(data),
  .vclk(vclk),.x(x),.y(y),.ce(ce),.visible(de),.hs(hs),.vs(vs),.field(field),
  .out_ce(oce),.out_visible(ode),.out_hs(oh),.out_vs(ov),.out_field(ofield),.rgb(rgb));
 function automatic integer byte_at(input integer at);
  byte_at=(ram[at>>3]>>((at&7)*8))&255;
 endfunction
 function automatic integer clamp(input integer v);clamp=v<0?0:v>255?255:v;endfunction
 integer base,pixel,entry,yy,cb,cr,er,eg,eb;
 reg [9:0] row;
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
 // The output pipeline is 3 video clocks; the raster row is stable for the
 // whole active line, so sample the row at the start of each output line.
 always @(negedge vclk)begin
  if(oce)begin
   line_samples=line_samples+1;
   if(last_oh && !oh)begin last_line_samples=line_samples;line_samples=0;end
   last_oh=oh;
   if(ode && !last_ode)begin column=0;row=y;end
   if(!ode && last_ode)begin
    lines=lines+1;if(column!=720)short_lines=short_lines+1;
   end
   last_ode=ode;
   if(ode)begin
    if(frames>=3)begin
     base=row[0]?32'h5b6a58:32'h584048;
     pixel=byte_at(base+(row>>1)*720+column);
     entry=byte_at(32'h5e9468+pixel*2)*256+byte_at(32'h5e9468+pixel*2+1);
     yy=((entry>>8)&63)*4;cb=((entry>>4)&15)*16-128;cr=(entry&15)*16-128;
     er=clamp($rtoi(1.164*(yy-16)+1.596*cr));
     eg=clamp($rtoi(1.164*(yy-16)-0.392*cb-0.813*cr));
     eb=clamp($rtoi(1.164*(yy-16)+2.017*cb));
     if($signed({1'b0,rgb[23:16]})<er-2 || $signed({1'b0,rgb[23:16]})>er+2 ||
        $signed({1'b0,rgb[15:8]})<eg-2 || $signed({1'b0,rgb[15:8]})>eg+2 ||
        $signed({1'b0,rgb[7:0]})<eb-2 || $signed({1'b0,rgb[7:0]})>eb+2)begin
      if(bad<5)$display("mismatch x%d y%d got%h expected%d,%d,%d",column,row,rgb,er,eg,eb);
      bad=bad+1;
     end
     checked=checked+1;
    end
    column=column+1;
   end
  end
 end
 reg[31:0] prior;
 initial begin
  $readmemh("re/fpga_guide_checkpoint/ram64.hex",ram);
  repeat(4)@(negedge clk);reset=0;
  wait(frames==3);prior=underruns;
  wait(frames==6);@(negedge clk);
  if(error!=0 || underruns!=prior || bad!=0 || checked<3*288*720 || short_lines!=0 || last_line_samples!=864)
   $fatal(1,"video errors %h underruns%d->%d bad%d checked%d short%d line_samples%d",
          error,prior,underruns,bad,checked,short_lines,last_line_samples);
  $display("PASS: 720 samples/line 1:1 guest pixels, 864-sample lines, async 54/50 MHz, no new underruns; checked %d",checked);$finish;
 end
 initial begin #200000000;$fatal(1,"video timeout");end
endmodule
