// SPDX-License-Identifier: GPL-3.0-only
// Replays an explicitly loaded, packet-aligned TS file through the existing
// MiSTer DDR bridge. HPS transfers bytes; all consumption runs in the FPGA.
module pace_ts_replay #(
 parameter [28:0] BASE=29'h06600000,
 parameter integer BYTE_CLOCKS=400 // 50MHz / 400 * 8 = 1 Mbit/s, no PCR claim
)(
 input wire clk,reset,hold,enabled,
 input wire [23:0] length,
 output wire valid,input wire ready,output wire [7:0] data,
 output reg [31:0] loops=0,
 output wire mem_req,output wire [28:0] mem_addr,
 input wire mem_accept,mem_rvalid,input wire [63:0] mem_rdata
);
 reg [23:0] position=0;
 reg [63:0] cache=0;
 reg cache_valid=0,waiting=0;
 reg [15:0] delay=0;
 assign mem_req=enabled && !hold && !cache_valid && !waiting && length!=0;
 assign mem_addr=BASE+{8'd0,position[23:3]};
 assign valid=enabled && !hold && cache_valid && delay==0 && length!=0;
 assign data=cache[position[2:0]*8+:8];
 always @(posedge clk)begin
  if(reset)begin position<=0;cache_valid<=0;waiting<=0;delay<=0;loops<=0;end
  else begin
   if(mem_accept)waiting<=1;
   if(mem_rvalid)begin cache<=mem_rdata;cache_valid<=1;waiting<=0;end
   if(!hold)begin
    if(delay!=0)delay<=delay-1'b1;
    if(valid && ready)begin
     delay<=16'(BYTE_CLOCKS-1);
     if(position+1'b1>=length)begin position<=0;cache_valid<=0;loops<=loops+1'b1;end
     else begin position<=position+1'b1;if(position[2:0]==7)cache_valid<=0;end
    end
   end
  end
 end
endmodule
