`timescale 1ns/1ps
module tb_keyboard_remote;
 reg clk=0,reset=1;always #5 clk=~clk;
 reg [10:0] key=0;wire valid,pressed;wire[7:0] code;wire[31:0] count;
 pace_keyboard_remote dut(clk,reset,key,valid,pressed,code,count);
 task send(input[8:0] scan,input down,input[7:0] expected);
 begin
  @(negedge clk);key={!key[10],down,scan};@(negedge clk);
  if(!valid || pressed!==down || code!==expected)$fatal(1,"mapping %h got %h",scan,code);
  @(negedge clk);if(valid)$fatal(1,"duplicate held toggle");
 end endtask
 initial begin
 repeat(3)@(negedge clk);reset=0;
 send(9'h005,1,8'hCC);send(9'h005,0,8'hCC);
 send(9'h006,1,8'h7D);send(9'h006,0,8'h7D);
 send(9'h004,1,8'h7E);send(9'h004,0,8'h7E);
 send(9'h00C,1,8'hF5);send(9'h00C,0,8'hF5);
 send(9'h003,1,8'h80);send(9'h003,0,8'h80);
 send(9'h00B,1,8'hCB);send(9'h00B,0,8'hCB);
 send(9'h083,1,8'h81);send(9'h083,0,8'h81);
 send(9'h00A,1,8'h3C);send(9'h00A,0,8'h3C);
 send(9'h001,1,8'h0C);send(9'h001,0,8'h0C);
 send(9'h009,1,8'h84);send(9'h009,0,8'h84);
 send(9'h175,1,8'h58);send(9'h175,0,8'h58);
 send(9'h172,1,8'h59);send(9'h172,0,8'h59);
 send(9'h16B,1,8'h5A);send(9'h16B,0,8'h5A);
 send(9'h174,1,8'h5B);send(9'h174,0,8'h5B);
 send(9'h05A,1,8'h5C);send(9'h05A,0,8'h5C);
 send(9'h15A,1,8'h5C);send(9'h15A,0,8'h5C);
 send(9'h076,1,8'h83);send(9'h076,0,8'h83);
 send(9'h066,1,8'h83);send(9'h066,0,8'h83);
 send(9'h17D,1,8'h20);send(9'h17D,0,8'h20);
 send(9'h17A,1,8'h21);send(9'h17A,0,8'h21);
 send(9'h02D,1,8'h6D);send(9'h02D,0,8'h6D);
 send(9'h034,1,8'h6E);send(9'h034,0,8'h6E);
 send(9'h035,1,8'h6F);send(9'h035,0,8'h6F);
 send(9'h032,1,8'h70);send(9'h032,0,8'h70);
 send(9'h043,1,8'hCB);send(9'h043,0,8'hCB);
 send(9'h033,1,8'h81);send(9'h033,0,8'h81);
 send(9'h02C,1,8'h3C);send(9'h02C,0,8'h3C);
 send(9'h01B,1,8'h80);send(9'h01B,0,8'h80);
 send(9'h04D,1,8'h0C);send(9'h04D,0,8'h0C);
 send(9'h029,1,8'h3E);send(9'h029,0,8'h3E);
 send(9'h03B,1,8'h24);send(9'h03B,0,8'h24);
 send(9'h042,1,8'h3F);send(9'h042,0,8'h3F);
 send(9'h021,1,8'h40);send(9'h021,0,8'h40);
 send(9'h054,1,8'h3D);send(9'h054,0,8'h3D);
 send(9'h05B,1,8'h28);send(9'h05B,0,8'h28);
 send(9'h045,1,8'h00);send(9'h045,0,8'h00);
 send(9'h016,1,8'h01);send(9'h016,0,8'h01);
 send(9'h01E,1,8'h02);send(9'h01E,0,8'h02);
 send(9'h026,1,8'h03);send(9'h026,0,8'h03);
 send(9'h025,1,8'h04);send(9'h025,0,8'h04);
 send(9'h02E,1,8'h05);send(9'h02E,0,8'h05);
 send(9'h036,1,8'h06);send(9'h036,0,8'h06);
 send(9'h03D,1,8'h07);send(9'h03D,0,8'h07);
 send(9'h03E,1,8'h08);send(9'h03E,0,8'h08);
 send(9'h046,1,8'h09);send(9'h046,0,8'h09);
 @(negedge clk);key={!key[10],1'b1,9'h007};@(negedge clk);
 if(valid)$fatal(1,"F12 must stay reserved for MiSTer OSD");
 if(count!==90)$fatal(1,"event count %d",count);
 $display("PASS: all 45 mapped keys, make/break, no duplicates, F12 reserved");$finish;
 end
endmodule
