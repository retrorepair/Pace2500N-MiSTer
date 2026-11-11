// SPDX-License-Identifier: GPL-3.0-only
// Replays a transport stream from DDR at the broadcast rate. HPS transfers
// bytes; all consumption runs in the FPGA.
//  - File mode: an explicitly loaded, packet-aligned TS file of `length`
//    bytes, looped.
//  - Stream mode (`stream`): a ring of `length` (power of two) bytes filled by
//    pace_ts_stream; bytes are consumed only below `available` (bytes written
//    so far), and `played` counts bytes consumed since the stream started.
module pace_ts_replay #(
 parameter [28:0] BASE=29'h06600000,
 parameter integer BYTE_CLOCKS=400, // 50MHz / 400 * 8 = 1 Mbit/s: SI-only replay files (<= 1 MiB)
 parameter integer FAST_BYTE_CLOCKS=64 // 50MHz / 64 * 8 = 6.25 Mbit/s: A/V streams (tools/sky_mux.py)
)(
 input wire clk,reset,hold,enabled,
 input wire [26:0] length,
 input wire fast,
 input wire stream,
 input wire [31:0] available,
 output reg [31:0] played=0,
 output reg [31:0] underruns=0,
 output wire valid,input wire ready,output wire [7:0] data,
 output reg [31:0] loops=0,
 output wire mem_req,output wire [28:0] mem_addr,
 input wire mem_accept,mem_rvalid,input wire [63:0] mem_rdata
);
 reg [26:0] position=0;
 reg [63:0] cache=0;
 reg cache_valid=0,waiting=0;
 reg [15:0] delay=0;
 // Stream mode: the 64-bit word holding `position` must be completely written.
 // The byte counters are free-running and wrap at 4 GiB (~91 minutes at
 // 6.25 Mbit/s), so compare their modular difference, never their values.
 wire [31:0] ahead=available-{played[31:3],3'b000};
 wire word_ready=!stream || (ahead>=32'd8 && !ahead[31]);
 assign mem_req=enabled && !hold && !cache_valid && !waiting && length!=0 && word_ready;
 assign mem_addr=BASE+{5'd0,position[26:3]};
 assign valid=enabled && !hold && cache_valid && delay==0 && length!=0;
 assign data=cache[position[2:0]*8+:8];
 always @(posedge clk)begin
  if(reset)begin position<=0;cache_valid<=0;waiting<=0;delay<=0;loops<=0;played<=0;underruns<=0;end
  else begin
   if(mem_accept)waiting<=1;
   if(mem_rvalid)begin cache<=mem_rdata;cache_valid<=1;waiting<=0;end
   if(!hold)begin
    if(delay!=0)delay<=delay-1'b1;
    // Starved stream: the next word is not in the ring yet when a byte is due.
    if(stream && enabled && !cache_valid && !waiting && !word_ready && delay==0)underruns<=underruns+1'b1;
    if(valid && ready)begin
     delay<=fast ? 16'(FAST_BYTE_CLOCKS-1) : 16'(BYTE_CLOCKS-1);
     played<=played+32'd1;
     if(position+1'b1>=length)begin position<=0;cache_valid<=0;loops<=loops+1'b1;end
     else begin position<=position+1'b1;if(position[2:0]==7)cache_valid<=0;end
    end
   end
  end
 end
endmodule
