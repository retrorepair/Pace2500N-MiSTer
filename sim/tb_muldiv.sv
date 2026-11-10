`timescale 1ns/1ps
module tb_muldiv;
 reg clk=0,reset=1,start=0; always #5 clk=~clk;
 reg [1:0] operation; reg [31:0] a,b;
 wire busy,done,error; wire [31:0] hi,lo;
 pace_muldiv dut(.*);
 integer n,k; reg [63:0] expected; reg signed [63:0] sa,sb;
 task check(input [1:0] op,input [31:0] x,y);
 begin
  @(negedge clk);operation=op;a=x;b=y;start=1;
  @(negedge clk);start=0;k=0;
  while(!done && k<40)begin @(negedge clk);k=k+1;end
  if(!done || busy)$fatal(1,"arithmetic timeout");
  if(op[1] && y==0)begin if(!error)$fatal(1,"missing divide-zero diagnostic");end
  else begin
   sa=$signed(x);sb=$signed(y);
   case(op)
    0:expected=sa*sb;
    1:expected={32'd0,x}*{32'd0,y};
    2:begin expected[31:0]=sa/sb;expected[63:32]=sa%sb;end
    3:begin expected[31:0]=x/y;expected[63:32]=x%y;end
   endcase
   if(error || {hi,lo}!==expected)$fatal(1,"op%0d %h %h got%h expected%h",op,x,y,{hi,lo},expected);
  end
 end endtask
 initial begin
  repeat(3)@(negedge clk);reset=0;
  for(n=0;n<4;n=n+1)begin
   check(n,0,0);check(n,0,1);check(n,32'h80000000,32'hffffffff);
   check(n,32'hffffffff,32'hffffffff);check(n,32'h80000000,1);
   check(n,32'h80000000,32'h80000000);check(n,32'hffffffff,2);
   repeat(500)check(n,$random,$random);
  end
  @(negedge clk);operation=3;a=100;b=3;start=1;
  @(negedge clk);start=0;repeat(5)@(negedge clk);reset=1;
  @(negedge clk);if(busy || done || error)$fatal(1,"reset did not flush arithmetic");
  $display("PASS: 2028 arithmetic cases and reset");$finish;
 end
endmodule
