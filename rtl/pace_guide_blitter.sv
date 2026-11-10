// SPDX-License-Identifier: GPL-3.0-only
// Actual guest DMA12 packets:418F fill16,01AC index8 fill,00AC packed copy.
// No host text/assets. Completion asserts only after all RAM writes finish.
module pace_guide_blitter (
 input wire clk,reset,hold,start,
 input wire [31:0] descriptor,
 output reg done=0,
 output wire busy,
 output reg [7:0] error=0,
 output reg [31:0] completions=0,last_opcode=0,
 output reg mem_req=0,mem_we=0,
 output reg [28:0] mem_addr=0,
 output reg [63:0] mem_wdata=0,
 output reg [7:0] mem_be=0,
 input wire mem_accept,mem_rvalid,
 input wire [63:0] mem_rdata
);
 localparam IDLE=0,READ_REQ=1,READ_WAIT=2,DECODE_DESC=3,DECODE_CMD=4,
            PIXEL=5,SOURCE_REQ=6,SOURCE_WAIT=7,WRITE_REQ=8,NEXT_PIXEL=9;
 reg [3:0] state=0;
 reg command_phase=0;
 reg [4:0] word_index=0;
 reg [31:0] words[0:14],desc[0:9];
 reg [31:0] read_base=0,read_address=0;
 reg [23:0] source=0,base_even=0,base_odd=0;
 reg [11:0] stride=0,width=0;
 reg [10:0] height=0,x=0,y=0,column=0,row=0;
 reg [15:0] even_color=0,odd_color=0;
 reg fill16=0,copy8=0;
 reg [63:0] source_cache=0;
 reg [20:0] source_tag=0;
 reg source_valid=0;
 reg [23:0] pixel_destination=0,pixel_source=0;
 reg [7:0] pixel_value=0;
 wire [11:0] frame_line=y+row;
 wire [31:0] src_offset={8'd0,source}+row*width+column;
 wire [31:0] dest_offset=fill16 ? ({8'd0,base_even}+(y+row)*stride+(x+column)*2) :
                  ({8'd0,(frame_line[0]?base_odd:base_even)}+(frame_line>>1)*stride+x+column);
 assign busy=state!=IDLE;
 function automatic [31:0] be_word(input[63:0] data,input upper);
  reg[31:0] part;
  begin part=upper?data[63:32]:data[31:0];be_word={part[7:0],part[15:8],part[23:16],part[31:24]};end
 endfunction
 always @(posedge clk)begin
  done<=0;
  if(reset)begin state<=IDLE;mem_req<=0;source_valid<=0;error<=0;completions<=0;last_opcode<=0;end
  else if(!hold && error==0)begin
   if(start && state!=IDLE)error<=8'hb0;
   case(state)
    IDLE:if(start)begin
     if(descriptor>=32'h01000000 || descriptor[1:0]!=0)error<=8'hb1;
     else begin read_base<=descriptor;word_index<=0;command_phase<=0;state<=READ_REQ;end
    end
    READ_REQ:begin
     read_address<=read_base+{25'd0,word_index,2'b00};
     mem_req<=1;mem_we<=0;mem_addr<=29'h06000000+((read_base+{25'd0,word_index,2'b00})>>3);mem_be<=8'hff;
     if(mem_req && mem_accept)begin mem_req<=0;state<=READ_WAIT;end
    end
    READ_WAIT:if(mem_rvalid)begin
     if(command_phase)words[word_index]<=be_word(mem_rdata,read_address[2]);
     else desc[word_index]<=be_word(mem_rdata,read_address[2]);
     if(word_index==(command_phase?14:9))state<=command_phase?DECODE_CMD:DECODE_DESC;
     else begin word_index<=word_index+1'b1;state<=READ_REQ;end
    end
    DECODE_DESC:begin
     if(desc[5]!=32'h0014003c || desc[8]-desc[3]!=59 || desc[3]>=32'h01000000)error<=8'hb2;
     else begin read_base<=desc[3];word_index<=0;command_phase<=1;state<=READ_REQ;end
    end
    DECODE_CMD:begin
     last_opcode<=words[0];source<=words[1][23:0];base_even<=words[7][23:0];base_odd<=words[8][23:0];
     fill16<=words[0]==32'h418f0000;copy8<=words[0]==32'h00ac0000;
     even_color<=words[14][31:16];odd_color<=words[14][15:0];
     stride<=({1'b0,words[11][10:0]}+1)*(words[0]==32'h418f0000 ? 2 : 1);
     x<=words[12][10:0];y<=words[12][26:16];
     width<={1'b0,words[13][10:0]}+1;height<={1'b0,words[13][25:16]}+1;
     column<=0;row<=0;source_valid<=0;
     if(words[0]!=32'h418f0000 && words[0]!=32'h01ac0000 && words[0]!=32'h00ac0000)error<=8'hb3;
     else if(words[7]>=32'h01000000 || words[8]>=32'h01000000 ||
       ({1'b0,words[12][10:0]}+{1'b0,words[13][10:0]}+1) > ({1'b0,words[11][10:0]}+1))error<=8'hb4;
     else if(words[0]==32'h00ac0000 && words[1]>=32'h01000000)error<=8'hb5;
     else state<=PIXEL;
    end
    PIXEL:begin
     pixel_destination<=dest_offset[23:0];pixel_source<=src_offset[23:0];
     if(dest_offset>=32'h01000000 || (copy8 && src_offset>=32'h01000000))error<=8'hb6;
     else if(copy8)begin
      if(source_valid && source_tag==src_offset[23:3])begin
       pixel_value<=source_cache[src_offset[2:0]*8+:8];state<=WRITE_REQ;
      end else state<=SOURCE_REQ;
     end else begin pixel_value<=frame_line[0]?odd_color[7:0]:even_color[7:0];state<=WRITE_REQ;end
    end
    SOURCE_REQ:begin
     mem_req<=1;mem_we<=0;mem_addr<=29'h06000000+{8'd0,pixel_source[23:3]};mem_be<=8'hff;
     if(mem_req && mem_accept)begin mem_req<=0;state<=SOURCE_WAIT;end
    end
    SOURCE_WAIT:if(mem_rvalid)begin
     source_cache<=mem_rdata;source_tag<=pixel_source[23:3];source_valid<=1;
     pixel_value<=mem_rdata[pixel_source[2:0]*8+:8];state<=WRITE_REQ;
    end
    WRITE_REQ:begin
     mem_req<=1;mem_we<=1;mem_addr<=29'h06000000+{8'd0,pixel_destination[23:3]};
     mem_wdata<=fill16 ? ({48'd0,even_color[7:0],even_color[15:8]}<<(pixel_destination[2:0]*8)) :
                               ({56'd0,pixel_value}<<(pixel_destination[2:0]*8));
     mem_be<=(fill16?8'h03:8'h01)<<pixel_destination[2:0];
     if(mem_req && mem_accept)begin mem_req<=0;state<=NEXT_PIXEL;end
    end
    NEXT_PIXEL:begin
     if(column+1==width)begin
      column<=0;
      if(row+1==height)begin done<=1;completions<=completions+1'b1;state<=IDLE;end
      else begin row<=row+1'b1;state<=PIXEL;end
     end else begin column<=column+1'b1;state<=PIXEL;end
    end
    default:error<=8'hbf;
   endcase
  end
 end
endmodule
