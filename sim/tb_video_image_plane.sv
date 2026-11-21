`timescale 1ns/1ps
module tb_video_image_plane;
 reg clk=0,vclk=0;always #10 clk=~clk;always #9.25 vclk=~vclk;
 reg reset=1,bus_reset=1,hold=0,enable=1,access=0,we=0;
 reg [31:0] io_addr=0,io_wdata=0;wire hit;wire [31:0] io_rdata;
 wire req;wire [28:0] addr;wire [7:0] burst;reg accept=0,rvalid=0;reg [63:0] rdata=0;
 reg ce=0,visible=0,field=0;reg [9:0] x=0,y=0;wire [23:0] rgb;wire valid;wire [31:0] underruns;
 pace_video_image_plane dut(.*,.mem_req(req),.mem_addr(addr),.mem_burst(burst),
  .mem_accept(accept),.mem_rvalid(rvalid),.mem_rdata(rdata));
 localparam YEV='h100000,YODD=YEV+720*288,UVEV=YODD+720*288,UVODD=UVEV+720*144;
 integer generation=0,clocks=0,left=0,latency=0,reads=0;
 reg [28:0] next_word;
 function automatic [7:0] luminance(input integer row,col);
  luminance=generation ? 235:46+(row%70)+col/32;
 endfunction
 function automatic [7:0] uvalue(input integer row,col);
  uvalue=generation ? 128:151+row%11;
 endfunction
 function automatic [7:0] vvalue(input integer row,col);
  vvalue=generation ? 128:126+col%9;
 endfunction
 function automatic [63:0] memory(input [28:0] word_address);
  integer a,offset,row,col,i;reg chroma,odd;begin
   a=(word_address-29'h06000000)*8;
   if(a<YEV || a>=UVODD+720*144)$fatal(1,"Image read outside native planes %h",a);
   chroma=a>=UVEV;odd=chroma ? a>=UVODD:a>=YODD;
   offset=a-(chroma ? (odd?UVODD:UVEV):(odd?YODD:YEV));
   row=(offset/720)*2+int'(odd);col=offset%720;
   for(i=0;i<8;i=i+1)memory[i*8+:8]=chroma ?
     ((i&1)==0 ? uvalue(row,(col+i)/2):vvalue(row,(col+i)/2)):luminance(row,col+i);
  end
 endfunction
 always @(negedge clk)begin
  clocks=clocks+1;accept=left==0 && clocks%7!=0;rvalid=0;
  if(left!=0)begin
   if(latency>0)latency=latency-1;
   else if(clocks%6!=0)begin rvalid=1;rdata=memory(next_word);next_word=next_word+1;left=left-1;end
  end
 end
 always @(posedge clk)if(req && accept)begin
  if(left || burst==0 || burst>8)$fatal(1,"Bad/overlapping image burst");
  left=burst;next_word=addr;latency=3+clocks%5;reads=reads+1;
 end
 function automatic [7:0] clip(input integer a);
  clip=a<0?0:a>255?255:a;
 endfunction
 function automatic [23:0] expected(input integer row,col);
  integer a,b,c;begin
   a=int'(luminance(row,col))-16;b=int'(uvalue(row/2,col/2))-128;c=int'(vvalue(row/2,col/2))-128;
   expected={clip((298*a+409*c)>>>8),clip((298*a-100*b-208*c)>>>8),clip((298*a+516*b)>>>8)};
  end
 endfunction
 reg [9:0] xp[0:2],yp[0:2];reg [2:0] vp=0;integer checked=0;
 reg score=0;
 always @(posedge vclk)begin
  xp[0]<=x;yp[0]<=y;xp[1]<=xp[0];yp[1]<=yp[0];xp[2]<=xp[1];yp[2]<=yp[1];vp<={vp[1:0],visible};
  #1;
  if(score && vp[2])begin
   if(!valid)$fatal(1,"Image missing at %0d,%0d",xp[2],yp[2]);
   if(rgb!==expected(yp[2],xp[2]))$fatal(1,"Image RGB mismatch at %0d,%0d got%h expected%h",xp[2],yp[2],rgb,expected(yp[2],xp[2]));
   checked=checked+1;
  end
 end
 task automatic store(input [5:0] offset,input [31:0] value);
  @(negedge clk);access=1;we=1;io_addr=32'hb0004000+offset;io_wdata=value;
  @(negedge clk);access=0;we=0;
 endtask
 task automatic configure;
  store('h04,YEV);store('h0c,YODD);store('h08,UVEV);store('h10,UVODD);
  store('h14,32'h023f02cf);store('h24,32'h023f02cf);store('h34,32'h024002d0);store('h00,32'h07c1c001);
 endtask
 task automatic draw(input integer parity);
  integer row,col;begin
   @(negedge vclk);visible=0;ce=0;field=parity;y=parity;x=0;
   repeat(2500)@(negedge vclk);
   score=1;
   for(row=parity;row<parity+12;row=row+2)begin
    y=row;visible=1;
    for(col=0;col<720;col=col+1)begin
     x=col;ce=1;@(negedge vclk);ce=0;repeat(3)@(negedge vclk);
    end
    visible=0;ce=0;repeat(576)@(negedge vclk);
   end
   repeat(5)@(negedge vclk);score=0;
  end
 endtask
 integer saved_reads;
 initial begin
  repeat(10)@(negedge clk);bus_reset=0;reset=0;
  configure();draw(0);draw(1);
  if(checked<30000)$fatal(1,"Insufficient pixels checked");
  $display("PASS packed unsigned YUV420 fields, bursts, RGB and first/last pixels: %0d samples",checked);
  // Disable while a burst is outstanding. Old beats must drain; re-enable must
  // refetch instead of displaying line tags from the previous image generation.
  @(negedge vclk);field=0;
  wait(left>=4);store(0,0);repeat(300)@(negedge clk);
  if(valid || left!=0 || dut.state!=0)$fatal(1,"Disable did not drain accepted image burst");
  saved_reads=reads;repeat(100)@(negedge clk);
  if(reads!=saved_reads)$fatal(1,"Read continued while image disabled");
  generation=1;store(0,32'h07c1c001);draw(0);draw(1);
  $display("PASS TV/disable -> image restore, no stale colour or line tags");
  // A CPU reset must not abandon an already accepted bus burst.
  @(negedge vclk);field=0;wait(left>=4);
  @(negedge clk);reset=1;repeat(8)@(negedge clk);reset=0;
  repeat(300)@(negedge clk);
  if(left!=0 || dut.state!=0)$fatal(1,"Warm reset failed to drain image read");
  configure();draw(0);
  store('h14,32'h023f02bf);repeat(20)@(negedge vclk);
  if(valid)$fatal(1,"Unsupported image size displayed");
  $display("PASS image MMIO, warm-reset drain and unsupported-profile suppression");$finish;
 end
 initial begin #5000000;$fatal(1,"Image plane test timeout");end
endmodule
