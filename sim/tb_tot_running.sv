`timescale 1ns/1ps
// Running-clock check for pace_tot_clock: load 2026-12-31 23:59:58 and let
// CLK_HZ=100 clocks pass per second; expect 23:59:59, then 00:00:00 the next day.
module tb_tot_running;
 reg clk=0;always #10 clk=~clk;
 reg [64:0] rtc={1'b0,8'h04,8'h26,8'h12,8'h31,8'h23,8'h59,8'h58};
 wire [7:0] od;wire ir,ov;wire [31:0] rw;
 pace_tot_clock #(.CLK_HZ(100)) dut(.clk(clk),.reset(1'b0),.enable(1'b1),.rtc(rtc),.in_valid(1'b0),.in_ready(ir),.in_data(8'd0),
  .out_valid(ov),.out_ready(1'b1),.out_data(od),.rewritten(rw));
 initial begin
  repeat(5)@(posedge clk);
  $display("t0 mjd %0d hms %h",dut.mjd,dut.hms);
  repeat(100)@(posedge clk);$display("t1 mjd %0d hms %h",dut.mjd,dut.hms);
  repeat(100)@(posedge clk);$display("t2 mjd %0d hms %h",dut.mjd,dut.hms);
  if(dut.hms!==24'h000000 || dut.mjd!==16'd61406)$fatal(1,"rollover wrong");
  rtc={1'b1,8'h02,8'h26,8'h11,8'h10,8'h12,8'h34,8'h56};
  repeat(5)@(posedge clk);$display("reload mjd %0d hms %h",dut.mjd,dut.hms);
  if(dut.hms!==24'h123456 || dut.mjd!==16'd61354)$fatal(1,"reload wrong");
  repeat(550)@(posedge clk);$display("5.5s later hms %h",dut.hms);
  if(dut.hms!==24'h123501)$fatal(1,"advance wrong");
  $display("PASS running TOT clock");$finish;
 end
endmodule
