// SPDX-License-Identifier: GPL-3.0-only
// A/V PES extraction for the two elementary-stream PIDs the firmware programs
// into the EMMA demux (video B000A094, audio B000A098; bit 14 = enabled).
//
// Watches the same transport byte stream the section demux consumes (a pure
// tap: `ts_strobe` marks each byte actually transferred). For each selected
// PID it strips the TS header/adaptation field and the PES header and writes
// the elementary-stream bytes into a small FIFO for its decoder. The
// broadcast is real-time paced, so there is no back-pressure on the tap: if a
// decoder stalls long enough to fill its FIFO, bytes are dropped and counted.
module pace_av_pes #(parameter integer FIFO_BITS=12)(
 input wire clk,reset,
 input wire ts_strobe,input wire [7:0] ts_data,
 input wire [12:0] video_pid,audio_pid,input wire video_on,audio_on,
 output wire [7:0] video_data,output wire video_valid,input wire video_ready,
 output wire [7:0] audio_data,output wire audio_valid,input wire audio_ready,
 output reg [31:0] video_bytes=0,audio_bytes=0,
 output reg [15:0] video_dropped=0,audio_dropped=0
);
 // ---- transport packet walk
 reg [7:0] pos=0;                 // byte index within the 188-byte packet
 reg [12:0] pid=0;reg pusi=0,has_payload=0,has_adapt=0,sync_ok=0;
 reg [7:0] payload_start=4;       // index of the first payload byte
 wire is_video=video_on && pid==video_pid && pid!=13'h1fff;
 wire is_audio=audio_on && pid==audio_pid && pid!=13'h1fff;
 // ---- per-stream PES header skipping
 // skip: 0 = in ES payload, else state within the PES header
 //  1..3 start code 00 00 01, 4 stream_id, 5..6 length, 7..8 flags, 9 header_data_length, 10 skipping header data
 reg [3:0] v_state=0,a_state=0;reg [7:0] v_left=0,a_left=0;reg v_run=0,a_run=0;
 // The adaptation_field_length byte (index 4) is not payload.
 wire [7:0] first_index=(has_adapt && pos==8'd4) ? 8'hff : payload_start;
 wire in_payload=sync_ok && has_payload && pos>=first_index && pos>=8'd4;
 wire v_take=ts_strobe && in_payload && is_video;
 wire a_take=ts_strobe && in_payload && is_audio;
 // A payload_unit_start packet begins with a PES header: restart the walk at its first payload byte.
 wire first_payload=pos==first_index;
 wire [3:0] v_now=(pusi && first_payload) ? 4'd1 : v_state;
 wire [3:0] a_now=(pusi && first_payload) ? 4'd1 : a_state;
 wire v_es=v_take && v_now==0 && v_run;
 wire a_es=a_take && a_now==0 && a_run;
 function automatic [3:0] next_state(input [3:0] s,input [7:0] left);
  case(s)
   4'd0:next_state=4'd0;
   4'd9:next_state=4'd10;                       // header_data_length byte itself
   4'd10:next_state=left<=8'd1 ? 4'd0 : 4'd10;  // header data
   default:next_state=s+4'd1;
  endcase
 endfunction
 always @(posedge clk)begin
  if(reset)begin pos<=0;sync_ok<=0;v_state<=0;a_state<=0;v_run<=0;a_run<=0;
   video_bytes<=0;audio_bytes<=0;video_dropped<=0;audio_dropped<=0;end
  else begin
   if(!video_on)begin v_run<=0;v_state<=0;end
   if(!audio_on)begin a_run<=0;a_state<=0;end
   if(ts_strobe)begin
    pos<=pos==8'd187 ? 8'd0 : pos+8'd1;
    case(pos)
     8'd0:begin sync_ok<=ts_data==8'h47;payload_start<=8'd4;end
     8'd1:begin pusi<=ts_data[6];pid[12:8]<=ts_data[4:0];if(ts_data[7])sync_ok<=0;end
     8'd2:pid[7:0]<=ts_data;
     8'd3:begin has_adapt<=ts_data[5];has_payload<=ts_data[4];if(ts_data[7:6]!=0)sync_ok<=0;end // scrambled: not decoded
     8'd4:if(has_adapt)begin
      payload_start<=8'd5+ts_data;
      if(ts_data>8'd182)has_payload<=0;
     end
     default:begin end
    endcase
    if(v_take)begin
     if(v_now==4'd9)v_left<=ts_data;else if(v_now==4'd10)v_left<=v_left-8'd1;
     v_state<=(v_now==4'd9 && ts_data==0) ? 4'd0 : next_state(v_now,v_left);
     if(pusi && first_payload)v_run<=1;
    end
    if(a_take)begin
     if(a_now==4'd9)a_left<=ts_data;else if(a_now==4'd10)a_left<=a_left-8'd1;
     a_state<=(a_now==4'd9 && ts_data==0) ? 4'd0 : next_state(a_now,a_left);
     if(pusi && first_payload)a_run<=1;
    end
   end
   if(v_es)begin if(v_full)video_dropped<=video_dropped+1'b1;else video_bytes<=video_bytes+1'b1;end
   if(a_es)begin if(a_full)audio_dropped<=audio_dropped+1'b1;else audio_bytes<=audio_bytes+1'b1;end
  end
 end
 // ---- output FIFOs (first-word fall-through)
 wire v_full,a_full;
 pace_av_fifo #(.BITS(FIFO_BITS)) vfifo(.clk(clk),.reset(reset || !video_on),.wr(v_es && !v_full),.din(ts_data),.full(v_full),
  .dout(video_data),.valid(video_valid),.rd(video_valid && video_ready));
 pace_av_fifo #(.BITS(FIFO_BITS)) afifo(.clk(clk),.reset(reset || !audio_on),.wr(a_es && !a_full),.din(ts_data),.full(a_full),
  .dout(audio_data),.valid(audio_valid),.rd(audio_valid && audio_ready));
endmodule

// Small synchronous FIFO with registered block-RAM read and a held output byte.
module pace_av_fifo #(parameter integer BITS=12)(
 input wire clk,reset,wr,input wire [7:0] din,output wire full,
 output reg [7:0] dout=0,output reg valid=0,input wire rd
);
 (* ramstyle="M10K" *) reg [7:0] mem[0:(1<<BITS)-1];
 reg [BITS-1:0] wp=0,rp=0;reg [7:0] q=0;reg fetching=0;
 wire empty=wp==rp;
 assign full=(wp+1'b1)==rp;
 always @(posedge clk)begin
  q<=mem[rp];
  if(wr)mem[wp]<=din;
  if(reset)begin wp<=0;rp<=0;valid<=0;fetching<=0;end
  else begin
   if(wr)wp<=wp+1'b1;
   if(rd)valid<=0;
   // one-cycle RAM read, then present the byte until it is taken
   if(fetching)begin dout<=q;valid<=1;fetching<=0;end
   else if((!valid || rd) && !empty)begin rp<=rp+1'b1;fetching<=1;end
  end
 end
endmodule
