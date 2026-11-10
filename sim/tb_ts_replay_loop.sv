`timescale 1ns/1ps
module tb_ts_replay_loop;
 reg clk=0,reset=1;always #5 clk=~clk;
 reg[63:0] storage[0:23];
 wire request,accepted,valid,ready,hold;wire[28:0] address;wire[7:0] data;wire[31:0] loops;
 reg response=0,pending=0;reg[63:0] returned=0;reg[3:0] delay=0;
 integer cycle=0,bytes_seen=0,i,j;
 assign hold=cycle%71<5;assign ready=cycle%5>1;
 assign accepted=request && !pending && cycle%3!=0;
 pace_ts_replay #(.BYTE_CLOCKS(3)) dut(.clk(clk),.reset(reset),.hold(hold),.enabled(1'b1),.length(24'd188),
  .valid(valid),.ready(ready),.data(data),.loops(loops),
  .mem_req(request),.mem_addr(address),.mem_accept(accepted),.mem_rvalid(response),.mem_rdata(returned));
 always @(posedge clk)begin
  cycle<=cycle+1;response<=0;
  if(pending)begin if(delay==0)begin pending<=0;response<=1;end else delay<=delay-1'b1;end
  if(accepted)begin
   if(address<29'h06600000 || address>=29'h06600018)$fatal(1,"replay escaped 188-byte file");
   returned<=storage[address-29'h06600000];pending<=1;delay<=cycle%7;
  end
  if(!reset && valid && ready)begin
   if(data!=8'(bytes_seen%188==0?71:bytes_seen%188))$fatal(1,"loop byte %d got %h",bytes_seen,data);
   bytes_seen<=bytes_seen+1;
  end
 end
 initial begin
  for(i=0;i<24;i=i+1)for(j=0;j<8;j=j+1)storage[i][j*8+:8]=8'(i*8+j);
  storage[0][7:0]=8'h47;
  repeat(4)@(negedge clk);reset=0;
  while(bytes_seen<564)@(negedge clk);
  if(loops!=3)$fatal(1,"wrong loop count %d",loops);
  $display("PASS replay: three exact 188-byte loops, partial final DDR word, read/byte stalls and hold");$finish;
 end
 initial begin #1000000;$fatal(1,"timeout");end
endmodule
