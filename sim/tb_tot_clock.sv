`timescale 1ns/1ps
module tb_tot_clock;
 reg clk=0,reset=1;always #10 clk=~clk;
 reg [7:0] mem[0:112799];
 integer i=0,fd,n=112800;
 reg ready=0;
 wire in_ready,out_valid;wire [7:0] out_data;wire [31:0] rewritten;
 // RTC: 2026-11-10 12:34:56 (BCD), as hps_io presents it
 wire [64:0] rtc={1'b0,8'h02,8'h26,8'h11,8'h10,8'h12,8'h34,8'h56};
 pace_tot_clock dut(.clk(clk),.reset(reset),.enable(1'b1),.rtc(rtc),
  .in_valid(i<n),.in_ready(in_ready),.in_data(mem[i<n?i:0]),
  .out_valid(out_valid),.out_ready(ready),.out_data(out_data),.rewritten(rewritten));
 always @(posedge clk)begin
  ready<=$random;
  if(!reset && out_valid && ready)begin $fwrite(fd,"%02x\n",out_data);i<=i+1;end
 end
 initial begin
  $readmemh("sim/tot_in.hex",mem);fd=$fopen("sim/tot_out.hex","w");
  repeat(5)@(posedge clk);reset=0;
  wait(i==n);repeat(2)@(posedge clk);$fclose(fd);
  $display("DONE rewritten %0d",rewritten);$finish;
 end
endmodule
