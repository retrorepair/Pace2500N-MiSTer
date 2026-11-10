// SPDX-License-Identifier: GPL-3.0-only
// Video plane under the firmware OSD.
//
// The MPEG decoder runs its own 625-line raster on clk_dot (27 MHz, pixel
// repetition: each 13.5 MHz sample is held for two dots). clk_video (54 MHz)
// is the same PLL, phase-aligned 2x clock, so decoder outputs are sampled
// directly. `sync` tells the OSD raster where the decoder field starts (its
// first active sample), which locks the two rasters; the decoded picture is
// then shown wherever the OSD is transparent (`osd_key`). With no video the
// plane is BT.601 black, the backdrop colour the firmware programs
// (B00021C4 = 00808010).
module pace_video_mix #(parameter integer DEC_DELAY=1)(
 input wire clk_video,
 input wire [7:0] dec_r,dec_g,dec_b,input wire dec_en,dec_vs,input wire [11:0] dec_v,
 input wire show_video,
 output reg sync=0,sync_field=0,
 input wire [23:0] osd_rgb,input wire osd_key,osd_de,
 output wire [23:0] rgb,
 output wire dbg_en,output wire [23:0] dbg_rgb
);
 reg [24:0] line0=0,line1=0,line2=0,line3=0;   // {en,rgb} delay line
 reg vs1=0,vs2=0,armed=0,field1=0;
 always @(posedge clk_video)begin
  line0<={dec_en,dec_r,dec_g,dec_b};line1<=line0;line2<=line1;line3<=line2;
  vs1<=dec_vs;vs2<=vs1;field1<=dec_v[0];
  sync<=0;
  if(vs1!=vs2)armed<=1;
  // first active sample after a vertical sync
  if(armed && line0[24] && !line1[24])begin armed<=0;sync<=1;sync_field<=field1;end
 end
 wire [24:0] tap=DEC_DELAY==0 ? line0 : DEC_DELAY==1 ? line1 : DEC_DELAY==2 ? line2 : line3;
 assign dbg_en=tap[24];assign dbg_rgb=tap[23:0];
 assign rgb=!osd_de ? 24'd0 : !osd_key ? osd_rgb : (show_video && tap[24]) ? tap[23:0] : 24'd0;
endmodule
