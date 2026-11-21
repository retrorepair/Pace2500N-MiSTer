// SPDX-License-Identifier: GPL-3.0-only
// EMMA video-to-memory DMA7, full-size PAL interlaced still-image profile.
// 8000A4AC programs B00020D8/DC/E0 and a 40-byte DMA descriptor. Destination
// is BE word4, inclusive end word8, row width word5[13:0], destination gap
// word7. The measured first request is 720*288 bytes at 005E9678.
//
// This copies real decoder pixels, not a host bitmap. The decoder's DDR map
// has four planar frames, each {65536 Y,16384 U,16384 V} 64-bit words.
// mem_addr.v computes raster addresses (Y stride=2*mb_width, C stride=mb_width);
// motcomp_recon.v packs signed -128..127 pixels, leftmost in bits63:56.
// resample_bilinear.v adds128 for display; DMA7 must do the same for EMMA's
// unsigned image format. The decoder calls the U bank FRAME_n_CR and the V
// bank FRAME_n_CB (resample_addrgen STATE_WR_U/V), despite those names.
// Native image storage
// separates the two Y fields and the two interleaved Cb/Cr fields.
//
// The caller supplies a stable still-frame bank in clk. Keep that bank
// reserved while busy; frame_valid must mean decoded picture data is ready.
// Chroma supports both packed rows and the driver's alternate-row (720-byte
// gap) layout. Two field boundaries precede the first read. Other capture modes
// stop with D7, without acknowledging an unperformed transfer.
module pace_video_capture_dma(
 input wire clk,reset,hold,
 input wire start,stop,input wire [31:0] descriptor,
 input wire io_write,input wire [31:0] io_addr,io_wdata,
 input wire field_tick,frame_valid,input wire [1:0] frame_id,
 input wire [7:0] frame_mb_width,input wire [11:0] frame_width,frame_height,
 output wire busy,output reg done=0,output reg [7:0] error=0,
 output wire mem_req,mem_write,output wire [28:0] mem_addr,
 output wire [63:0] mem_wdata,output wire [7:0] mem_be,
 input wire mem_accept,mem_rvalid,input wire [63:0] mem_rdata
);
 localparam IDLE=0,DESC3=1,DESC4=2,DESC7=3,DESC8=4,WAIT_COPY=5,
            WAIT_FRAME=6,READ_Y=7,READ_CB=8,READ_CR=9,WRITE=10,FAILED=11;
 reg [3:0] state=IDLE;
 reg waiting=0,discard=0,copy_pending=0,seen_field=0;
 reg [28:0] desc=0;
 reg [31:0] destination=0,destination_end=0;
 reg [31:0] descriptor_control=0,descriptor_gap=0;
 reg [31:0] x_width=0,y_height=0,copy_control=0;
 reg chroma=0,field_one=0;
 reg [1:0] bank=0;
 reg [8:0] row=0;
 reg [9:0] source_row=0;
 reg [6:0] column_word=0;
 reg [63:0] y_word=0,cb_word=0,cr_word=0;

 function automatic [31:0] be_word(input [63:0] value,input upper);
  be_word=upper ? {value[39:32],value[47:40],value[55:48],value[63:56]} :
                  {value[7:0],value[15:8],value[23:16],value[31:24]};
 endfunction
 function automatic [63:0] raster_bytes(input [63:0] value);
  integer i;
  for(i=0;i<8;i=i+1)raster_bytes[i*8+:8]=value[63-i*8-:8]^8'h80;
 endfunction
 function automatic [63:0] chroma_bytes(input [63:0] cb,cr,input upper_half);
  integer i;
  for(i=0;i<4;i=i+1)begin
   chroma_bytes[(i*2)*8+:8]=cb[63-(upper_half ? 32:0)-i*8-:8]^8'h80;
   chroma_bytes[(i*2+1)*8+:8]=cr[63-(upper_half ? 32:0)-i*8-:8]^8'h80;
  end
 endfunction
 wire reading=state==DESC3 || state==DESC4 || state==DESC7 || state==DESC8 ||
              state==READ_Y || state==READ_CB || state==READ_CR;
 wire [28:0] descriptor_byte=desc+(state==DESC3 ? 29'd8 : state==DESC4 ? 29'd16 :
                                      state==DESC7 ? 29'd24 : 29'd32);
 wire [21:0] bank_base={20'd0,bank}*22'h018000;
 wire [21:0] source_offset=chroma ? ({12'd0,source_row}*22'd45)+{16'd0,column_word[6:1]} :
                                  ({12'd0,source_row}*22'd90)+{15'd0,column_word};
 wire [21:0] component_base=state==READ_CB ? 22'h010000 : state==READ_CR ? 22'h014000 : 22'd0;
 wire descriptor_read=state==DESC3 || state==DESC4 || state==DESC7 || state==DESC8;
 wire [31:0] copy_span=copy_control[10] ? (descriptor_gap==720 ? 32'd206640:32'd103680):32'd207360;
 assign busy=state!=IDLE && state!=FAILED;
 assign mem_req=(reading || state==WRITE) && !waiting && !discard && !hold && !reset && !start && !stop && error==0;
 assign mem_write=state==WRITE;
 assign mem_addr=state==WRITE ? 29'h06000000+{8'd0,destination[23:3]} :
                 descriptor_read ? 29'h06000000+{8'd0,descriptor_byte[23:3]} :
                 29'h07000000+{7'd0,bank_base+component_base+source_offset};
 assign mem_wdata=chroma ? chroma_bytes(cb_word,cr_word,column_word[0]) : raster_bytes(y_word);
 assign mem_be=8'hff;

 always @(posedge clk)begin
  done<=0;
  if(reset)begin
   state<=IDLE;waiting<=0;discard<=0;copy_pending<=0;seen_field<=0;error<=0;
   x_width<=0;y_height<=0;copy_control<=0;
  end else if(start || stop)begin
   waiting<=0;copy_pending<=0;seen_field<=0;
   if(waiting && !mem_rvalid)discard<=1;
   if(start && error==0)begin
    desc<=descriptor[28:0];state<=DESC3;
    if(descriptor[28:24]!=0 || descriptor[2:0]!=0 || descriptor[23:0]>24'hffffd8)begin
     error<=8'hd7;state<=FAILED;
    end
   end else state<=IDLE;
  end else if(discard)begin
   if(mem_rvalid)discard<=0;
  end else if(error==0)begin
   // An accepted DDR read can return while the core is held. Consume its beat;
   // hold prevents issuing the next transaction, not receiving the current one.
   if(io_write && !hold)case(io_addr)
    32'hb00020dc:x_width<=io_wdata;
    32'hb00020e0:y_height<=io_wdata;
    32'hb00020d8:if(io_wdata[0] && busy)begin copy_control<=io_wdata;copy_pending<=1;end
    default:begin end
   endcase
   if(mem_req && mem_accept && reading)waiting<=1;
   case(state)
    DESC3:if(waiting && mem_rvalid)begin
     waiting<=0;state<=DESC4;
     if(be_word(mem_rdata,1)!=0)begin error<=8'hd7;state<=FAILED;end
    end
    DESC4:if(waiting && mem_rvalid)begin
     waiting<=0;destination<=be_word(mem_rdata,0);descriptor_control<=be_word(mem_rdata,1);state<=DESC7;
     if(be_word(mem_rdata,0)>=32'h01000000 || (be_word(mem_rdata,0)&7)!=0)begin error<=8'hd7;state<=FAILED;end
    end
    DESC7:if(waiting && mem_rvalid)begin
     waiting<=0;descriptor_gap<=be_word(mem_rdata,1);state<=DESC8;
     if(be_word(mem_rdata,0)!=0)begin error<=8'hd7;state<=FAILED;end
    end
    DESC8:if(waiting && mem_rvalid)begin
     waiting<=0;destination_end<=be_word(mem_rdata,0);state<=WAIT_COPY;
    end
    WAIT_COPY:if(copy_pending)begin
     if((copy_control&32'hffff73fe)!=0 || !copy_control[15] ||
        x_width!=32'd720 || y_height!=32'd576 ||
        (descriptor_gap!=0 && !(copy_control[10] && descriptor_gap==720)) ||
        (descriptor_control&32'hffffc000)!=32'h001c0000 ||
        descriptor_control[13:0]!=14'd720 || destination_end>=29'h01000000 ||
        destination_end!=destination+copy_span-32'd1)begin
      error<=8'hd7;state<=FAILED;
     end else begin
      chroma<=copy_control[10];field_one<=copy_control[11];seen_field<=0;
      state<=WAIT_FRAME;
     end
    end
    WAIT_FRAME:if(field_tick && frame_valid)begin
     if(frame_mb_width!=45 || frame_width!=720 || frame_height!=576)begin error<=8'hd7;state<=FAILED;end
     else if(!seen_field)seen_field<=1;
     else begin
      bank<=frame_id;source_row<={9'd0,field_one};row<=0;column_word<=0;
      state<=chroma ? READ_CB : READ_Y;
     end
    end
    READ_Y:if(waiting && mem_rvalid)begin waiting<=0;y_word<=mem_rdata;state<=WRITE;end
    READ_CB:if(waiting && mem_rvalid)begin waiting<=0;cb_word<=mem_rdata;state<=READ_CR;end
    READ_CR:if(waiting && mem_rvalid)begin waiting<=0;cr_word<=mem_rdata;state<=WRITE;end
    WRITE:if(mem_req && mem_accept)begin
     destination<=destination+32'd8;
     if(column_word==89)begin
      destination<=destination+32'd8+descriptor_gap;
      column_word<=0;source_row<=source_row+10'd2;row<=row+1'b1;
      if(row==(chroma ? 9'd143 : 9'd287))begin state<=IDLE;copy_pending<=0;done<=1;end
      else state<=chroma ? READ_CB : READ_Y;
     end else begin
      column_word<=column_word+1'b1;
      state<=chroma ? (column_word[0] ? READ_CB : WRITE) : READ_Y;
     end
    end
    default:begin end
   endcase
  end
 end
endmodule
