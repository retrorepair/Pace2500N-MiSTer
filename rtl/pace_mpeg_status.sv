// SPDX-License-Identifier: GPL-3.0-only
// EMMA MPEG video decoder: interrupt status and header-information registers,
// driven by the real decoder's parser (rtl/pace_mpeg_video.sv events).
//
// Layout and semantics are those the firmware's own decoder driver uses
// (decompiled ISR 0x8000FDEC, registered on EMMA interrupt bit 0x400 by
// 0x8000F55C; "video started" 0x8000D9A4; masks from their literal pools;
// see CURRENT_STATUS.md):
//   B0002480/84/88  interrupt status, groups 1..3. The ISR acknowledges by
//                   writing the complement of the bits it handled, so a write
//                   keeps only the bits written as 1 (status &= wdata).
//   B0002490/94/98  interrupt enables for the three groups (firmware-owned;
//                   the peripheral CSR store keeps and returns them, this
//                   block only snoops them).
//   B0002120        bits 29:28 picture_structure of the picture being decoded
//   B0002154        bits 27:16 vertical_size, bits 11:0 horizontal_size
//   B0002158        bits 7:4 aspect_ratio_information
//   B000216C        GOP time code: pictures 5:0, seconds 11:6, minutes 18:13,
//                   hours 23:19
// Events (the ISR's handlers for these bits read the matching registers):
//   group 2 bit 31  sequence header parsed      (reads B0002158, B0002154)
//   group 2 bit 11  GOP header parsed           (reads B000216C)
//   group 1 bit 11  picture decoding starts     (reads B0002120)
//   group 3 bit 0   display field               (the ISR's per-field counters)
// Fields and bits whose meaning is not established from the firmware are not
// driven (read as 0).
module pace_mpeg_status(
 input wire clk,reset,
 // CPU accesses to the EMMA device space (one-cycle strobe when accepted)
 input wire access,input wire we,input wire [31:0] addr,wdata,
 output wire hit,                 // addr is a register this block answers for reads
 output reg [31:0] rdata,
 output wire irq,                 // to EMMA interrupt controller bit 0x400
 // decoder events (clk domain, one-cycle pulses) and their values
 input wire seq_evt,gop_evt,pic_evt,field_evt,
 input wire [11:0] seq_hsize,seq_vsize,input wire [3:0] seq_aspect,
 input wire [22:0] gop_time_code,input wire [1:0] pic_structure
);
 reg [31:0] st1=0,st2=0,st3=0,en1=0,en2=0,en3=0;
 reg [31:0] r120=0,r154=0,r158=0,r16c=0;
 wire w=access && we;
 always @(posedge clk)begin
  if(reset)begin
   st1<=0;st2<=0;st3<=0;en1<=0;en2<=0;en3<=0;r120<=0;r154<=0;r158<=0;r16c<=0;
  end else begin
   // enables: snooped firmware writes
   if(w && addr==32'hb0002490)en1<=wdata;
   if(w && addr==32'hb0002494)en2<=wdata;
   if(w && addr==32'hb0002498)en3<=wdata;
   // status: acknowledge (keep bits written as 1), then raise new events
   st1<=((w && addr==32'hb0002480) ? st1&wdata : st1) | (pic_evt ? 32'h00000800 : 32'd0);
   st2<=((w && addr==32'hb0002484) ? st2&wdata : st2) | (seq_evt ? 32'h80000000 : 32'd0) | (gop_evt ? 32'h00000800 : 32'd0);
   st3<=((w && addr==32'hb0002488) ? st3&wdata : st3) | (field_evt ? 32'h00000001 : 32'd0);
   // header information, as parsed
   if(seq_evt)begin r154<={4'd0,seq_vsize,4'd0,seq_hsize};r158<={24'd0,seq_aspect,4'd0};end
   if(gop_evt)r16c<={8'd0,gop_time_code[22:18],gop_time_code[17:12],1'b0,gop_time_code[11:6],gop_time_code[5:0]};
   if(pic_evt)r120<={2'd0,pic_structure,28'd0};
  end
 end
 assign hit=addr==32'hb0002480 || addr==32'hb0002484 || addr==32'hb0002488 ||
            addr==32'hb0002120 || addr==32'hb0002154 || addr==32'hb0002158 || addr==32'hb000216c;
 always @* case(addr)
  32'hb0002480:rdata=st1;
  32'hb0002484:rdata=st2;
  32'hb0002488:rdata=st3;
  32'hb0002120:rdata=r120;
  32'hb0002154:rdata=r154;
  32'hb0002158:rdata=r158;
  32'hb000216c:rdata=r16c;
  default:rdata=32'd0;
 endcase
 assign irq=((st1&en1)|(st2&en2)|(st3&en3))!=0;
endmodule
