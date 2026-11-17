`timescale 1ns/1ps
module tb_guide_still;
 reg clk=0;always #10 clk=~clk;
 reg reset=1,enable=0,ready=0,mem_rvalid=0,pending=0,bad=0,respond=1;
 reg [63:0] mem_rdata=0;
 wire req,valid,present;
 wire [28:0] addr;
 wire [7:0] data;
 localparam [28:0] BASE=29'h0608e260;
 localparam integer SIZE=16524;
 wire accept=req && !pending && !mem_rvalid;
 reg [28:0] saved_addr=0;
 integer cycle=0,received=0,byte_offset,i;
 function automatic [7:0] expected(input integer offset);
  reg [63:0] magic;
  begin
   magic=64'h2440022db3010000;
   expected=offset<8 ? magic[offset*8+:8] : 8'(offset*31+(offset>>8));
  end
 endfunction
 pace_guide_still dut(.clk(clk),.reset(reset),.enable(enable),.mem_req(req),.mem_addr(addr),
  .mem_accept(accept),.mem_rvalid(mem_rvalid),.mem_rdata(mem_rdata),.data(data),.valid(valid),.ready(ready),
  .present(present));
 always @(posedge clk)begin
  cycle<=cycle+1;ready<=cycle%5!=2;mem_rvalid<=0;
  if(accept)begin saved_addr<=addr;pending<=1;end
  if(pending && respond && cycle%7==2)begin
   byte_offset=(saved_addr-BASE)*8;
   for(i=0;i<8;i=i+1)mem_rdata[i*8+:8]<=expected(byte_offset+i) ^ {8{bad}};
   mem_rvalid<=1;pending<=0;
  end
  if(valid && ready)begin
   if(data!==expected(received%SIZE))$fatal(1,"Incorrect byte %0d",received);
   received<=received+1;
  end
 end
 initial begin
  repeat(3)@(negedge clk);reset=0;enable=1;respond=0;
  wait(pending);@(negedge clk);enable=0;
  repeat(4)@(negedge clk);enable=1;respond=1;
  wait(received==4*SIZE);
  repeat(20)@(negedge clk);
  if(!present || req || valid)$fatal(1,"Still did not finish");
  enable=0;
  repeat(4)@(negedge clk);
  if(present)$fatal(1,"Leaving the Guide did not clear the still");
  bad=1;enable=1;
  repeat(30)@(negedge clk);
  if(present || valid || received!=4*SIZE)$fatal(1,"Invalid source was decoded");
  $display("PASS: four byte-exact still sequences, cancellation, backpressure and absent image");
  $finish;
 end
 initial begin #25000000;$fatal(1,"Timeout");end
endmodule
