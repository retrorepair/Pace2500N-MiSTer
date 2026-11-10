// SPDX-License-Identifier: GPL-3.0-only
// Validates bounded, sequential wide-IOCTL transfers without a long divider.
module pace_ts_load_tracker(
 input wire clk,reset,download,wr,input wire [26:0] address,
 output reg loaded=0,output reg [23:0] length=0
);
 reg previous=0,nonempty=0,bad=0;
 reg [7:0] remainder=0;
 reg [26:0] last_address=0;
 always @(posedge clk)begin
  previous<=download;
  if(reset)begin previous<=0;loaded<=0;length<=0;nonempty<=0;bad<=0;remainder<=0;last_address<=0;end
  else begin
   if(download && !previous)begin
    loaded<=0;length<=0;nonempty<=0;bad<=0;remainder<=0;last_address<=0;
   end
   if(download && wr)begin
    nonempty<=1;last_address<=address;
    if(address==0)begin
     remainder<=2;
     if(previous && nonempty)bad<=1;
    end else begin
     remainder<=remainder==186?8'd0:remainder+8'd2;
     if(!previous || !nonempty || address!=last_address+27'd2)bad<=1;
    end
   end
   if(previous && !download)begin
    loaded<=nonempty && !bad && last_address<1048576 && remainder==0;
    length<=nonempty && !bad && last_address<1048576 && remainder==0 ? last_address[23:0]+24'd2:24'd0;
   end
  end
 end
endmodule
