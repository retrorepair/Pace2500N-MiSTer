`timescale 1ns/1ps
// Exercise real PAL-sized planes with bank 2, variable memory latency and stalls.
// pixel() is semantic UNSIGNED Y/U/V. The memory model encodes signed samples
// and the decoder's U-at10000/V-at14000 layout; the guest must receive pixel().
module tb_video_capture_dma;
 reg clk=0;always #5 clk=~clk;
 reg reset=1,hold=0,start=0,stop=0,io_write=0,field_tick=0,frame_valid=0;
 reg [31:0] io_addr=0,io_wdata=0;
 wire busy,done,req,we;wire [7:0] error,be;
 wire [28:0] addr;wire [63:0] wdata;
 reg accept=0,rvalid=0;reg [63:0] rdata=0;
 pace_video_capture_dma dut(.clk(clk),.reset(reset),.hold(hold),.start(start),.stop(stop),
  .descriptor(32'h00108b78),.io_write(io_write),.io_addr(io_addr),.io_wdata(io_wdata),
  .field_tick(field_tick),.frame_valid(frame_valid),.frame_id(2'd2),.frame_mb_width(8'd45),
  .frame_width(12'd720),.frame_height(12'd576),.busy(busy),.done(done),.error(error),
  .mem_req(req),.mem_write(we),.mem_addr(addr),.mem_wdata(wdata),.mem_be(be),
  .mem_accept(accept),.mem_rvalid(rvalid),.mem_rdata(rdata));

 integer clocks=0,delay_left=0,writes=0,completions=0;
 integer plane=0;reg bad_geometry=0,bad_descriptor=0,score=0,force_delay=0;
 reg [63:0] response;
 function automatic [7:0] pixel(input integer component,y,x);
  pixel=(component*73+y*11+(y>>5)*13+x*3+(x>>3)*7)&255;
 endfunction
 function automatic [63:0] descriptor_pair(input [31:0] low,high);
  integer b;begin
   for(b=0;b<4;b=b+1)begin
    descriptor_pair[b*8+:8]=low[31-b*8-:8];
    descriptor_pair[(b+4)*8+:8]=high[31-b*8-:8];
   end
  end
 endfunction
 function automatic [63:0] memory(input [28:0] a);
  integer off,component,y,x,b;begin
   case(a)
    29'h06021170:memory=descriptor_pair(0,0); // descriptor +8
    29'h06021171:memory=descriptor_pair(32'h005e9678,bad_descriptor ? 32'h001402d0:32'h001c02d0);
    29'h06021172:memory=descriptor_pair(0,plane>=4 ? 720:0);
    29'h06021173:memory=descriptor_pair(32'h005e9678+(plane>=4 ? 206640 : plane>=2 ? 103680:207360)-1,0);
    default:begin
     if(a<29'h07030000 || a>=29'h07048000)$fatal(1,"Wrong picture bank/address %h",a);
     off=a-29'h07030000;
     component=off>=20'h14000 ? 2 : off>=20'h10000 ? 1 : 0;
     if(component!=0)off=off-(component==1 ? 20'h10000:20'h14000);
     y=off/(component==0 ? 90:45);x=(off%(component==0 ? 90:45))*8;
     for(b=0;b<8;b=b+1)memory[63-b*8-:8]=pixel(component,y,x+b)^8'h80;
    end
   endcase
  end
 endfunction
 always @(negedge clk)begin
  clocks=clocks+1;
  accept=(clocks%7!=0 && clocks%11!=0);
  hold=(clocks%97==0);
  field_tick=clocks%31==0;
  rvalid=0;
  if(delay_left!=0)begin
   delay_left=delay_left-1;
   if(delay_left==0)begin rvalid=1;rdata=response;end
  end
 end
 integer b,row,column,component,sample_x;
 always @(posedge clk)begin
  if(req && accept)begin
   if(we)begin
    if(!score)$fatal(1,"Unexpected write");
    if(addr!=29'h060bd2cf+writes+(plane>=4 ? (writes/90)*90:0) || be!=8'hff)$fatal(1,"Destination %h at word %0d",addr,writes);
    row=(writes/90)*2+(plane&1);column=(writes%90)*8;
    for(b=0;b<8;b=b+1)begin
     component=plane<2 ? 0 : (b%2==0 ? 1:2);
     sample_x=plane<2 ? column+b : (column+b)/2;
     if(wdata[b*8+:8]!==pixel(component,row,sample_x))
      $fatal(1,"Pixel plane%0d row%0d x%0d lane%0d got%h expected%h",plane,row,sample_x,b,wdata[b*8+:8],pixel(component,row,sample_x));
    end
    writes=writes+1;
   end else begin
    if(delay_left!=0)$fatal(1,"Overlapping reads");
    response=memory(addr);delay_left=force_delay ? 23 : 2+(clocks%5);
   end
  end
  if(done)begin
   if(writes!=(plane>=2 ? 12960:25920))$fatal(1,"Early completion after %0d writes",writes);
   completions=completions+1;
  end
 end
 task automatic store(input [31:0] a,d);
  @(negedge clk);io_addr=a;io_wdata=d;io_write=1;
  @(negedge clk);io_write=0;
 endtask
 task automatic launch;
  @(negedge clk);start=1;
  @(negedge clk);start=0;
  store(32'hb00020dc,bad_geometry ? 704:720);
  store(32'hb00020e0,576);
  store(32'hb00020d8,32'h8001|((plane&1)<<11)|(plane>=2 ? 32'h400:0));
 endtask
 integer guard,old_done;
 initial begin
  repeat(5)@(negedge clk);reset=0;
  // A stopped descriptor read still returns a beat. Restart must discard it.
  force_delay=1;launch();
  wait(dut.waiting);@(negedge clk);stop=1;
  @(negedge clk);stop=0;start=1;
  @(negedge clk);start=0;
  repeat(80)@(negedge clk);
  if(error || done || writes)$fatal(1,"Stop/restart consumed stale descriptor");
  @(negedge clk);stop=1;@(negedge clk);stop=0;
  repeat(30)@(negedge clk);force_delay=0;
  // Stop after a pixel read has been accepted, before it can produce a write.
  force_delay=1;score=1;frame_valid=1;launch();
  wait(dut.state==7 && dut.waiting);
  @(negedge clk);stop=1;@(negedge clk);stop=0;
  repeat(60)@(negedge clk);force_delay=0;
  if(writes || completions || busy || error)$fatal(1,"Stopped pixel read wrote data or completed");
  for(plane=0;plane<6;plane=plane+1)begin
   writes=0;score=1;frame_valid=0;old_done=completions;
   launch();repeat(120)@(negedge clk);
   if(writes || done || error)$fatal(1,"Copied without a decoded frame");
   frame_valid=1;guard=0;
   while(completions==old_done && !error && guard<600000)begin @(negedge clk);guard=guard+1;end
   if(error || completions==old_done)$fatal(1,"Copy failed: plane%0d error%h state%0d",plane,error,dut.state);
   repeat(4)@(negedge clk);
   if(busy || done)$fatal(1,"Completion was not a pulse");
   $display("PASS plane %0d: %0d checked bytes",plane,writes*8);
  end
  score=0;plane=0;bad_geometry=1;launch();repeat(200)@(negedge clk);
  if(error!=8'hd7 || done || busy)$fatal(1,"Unsupported geometry acknowledged");
  @(negedge clk);reset=1;repeat(3)@(negedge clk);reset=0;
  bad_geometry=0;bad_descriptor=1;launch();repeat(200)@(negedge clk);
  if(error!=8'hd7 || done || busy)$fatal(1,"Unsupported descriptor direction acknowledged");
  $display("PASS video capture: all fields, Cb/Cr, latency, stop/restart and invalid geometry");$finish;
 end
 initial begin #50000000;$fatal(1,"Timeout");end
endmodule
