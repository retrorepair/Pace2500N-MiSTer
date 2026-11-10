// SPDX-License-Identifier: GPL-3.0-only
// Actual guest DMA12 packets:418F fill16,01AC index8 fill,00AC packed copy.
// No host text/assets. Completion asserts only after all RAM writes finish.
//
// Word-wide DMA model. Each destination row is written as whole 64-bit DDR
// words with byte enables. For 00AC copies the row's source span is first
// burst-read (DDRAM burst, <=64 beats per request) into an on-chip row
// buffer, then streamed out through a fixed byte shift.
//
// Why this matters for fidelity: the Guide rasterises text into one shared
// source buffer (0x55C288) through KSEG1 (uncached, loop at 80000E4C) and
// refills it while the previous copy is still in flight. On the receiver,
// uncached VR4110 stores are slow bus transactions and the EMMA DMA moves
// data in bursts, so a copy always captures its source before the CPU can
// overwrite it. The earlier one-DDR-transaction-per-pixel model was slow
// enough for the CPU to overtake it, which corrupted the Guide.
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
 output reg [7:0] mem_burst=1,
 input wire mem_accept,mem_rvalid,
 input wire [63:0] mem_rdata
);
 localparam IDLE=0,READ_REQ=1,READ_WAIT=2,DECODE_DESC=3,DECODE_CMD=4,
            ROW_START=5,BURST_REQ=6,BURST_WAIT=7,PRIME=8,PRIME_WAIT=9,
            EMIT=10,WRITE_REQ=11,ROW_END=12;
 reg [3:0] state=0;
 reg command_phase=0;
 reg [4:0] word_index=0;
 reg [31:0] words[0:14],desc[0:9];
 reg [31:0] read_base=0,read_address=0;
 reg [23:0] source=0,base_even=0,base_odd=0;
 reg [11:0] stride=0,width=0;
 reg [10:0] height=0,x=0,y=0,row=0;
 reg [15:0] even_color=0,odd_color=0;
 reg fill16=0,copy8=0;
 // Row geometry (byte addresses within guest RAM).
 reg [23:0] dest_start=0,src_start=0;
 reg [12:0] dest_bytes=0;
 reg [8:0] dest_words=0,dest_index=0;
 reg [7:0] src_words=0,buf_fill=0,burst_left=0;
 reg signed [4:0] shift=0;  // src_lane - dest_lane, -7..7
 // Source row buffer, written by burst beats, read sequentially.
 (* ramstyle="M10K" *) reg [63:0] row_buf[0:127];
 reg [6:0] buf_raddr=0;
 reg [63:0] buf_q=0,lo_word=0;
 always @(posedge clk)begin
  buf_q<=row_buf[buf_raddr];
  if(state==BURST_WAIT && mem_rvalid)row_buf[buf_fill[6:0]]<=mem_rdata;
 end
 wire [11:0] frame_line=y+row;
 assign busy=state!=IDLE;
 function automatic [31:0] be_word(input[63:0] data,input upper);
  reg[31:0] part;
  begin part=upper?data[63:32]:data[31:0];be_word={part[7:0],part[15:8],part[23:16],part[31:24]};end
 endfunction
 // Destination word for dest_index: bytes from the {buf_q,lo_word} window
 // (copy) or the fill colour, with enables for bytes inside the row.
 reg [63:0] word_data;reg [7:0] word_be;
 wire [127:0] window={buf_q,lo_word};
 wire [3:0] base_pos=shift<0 ? shift+5'sd8 : shift;
 integer lane;
 reg signed [15:0] g;      // destination byte index within the row
 reg [3:0] pos;
 always @* begin
  word_data=0;word_be=0;
  for(lane=0;lane<8;lane=lane+1)begin
   g=$signed({3'b000,dest_index,3'b000})+lane-$signed({13'd0,dest_start[2:0]});
   pos=lane[3:0]+base_pos;
   if(g>=0 && g<$signed({3'b000,dest_bytes}))begin
    word_be[lane]=1'b1;
    if(copy8)word_data[lane*8+:8]=window[pos*8+:8];
    else if(fill16)word_data[lane*8+:8]=g[0] ? even_color[7:0] : even_color[15:8];
    else word_data[lane*8+:8]=frame_line[0] ? odd_color[7:0] : even_color[7:0];
   end
  end
 end
 // Row-buffer word supplying the window's high half for dest_index.
 wire [8:0] hi_index=dest_index+(shift<0 ? 9'd0 : 9'd1);
 wire [31:0] row_dest=fill16 ? ({8'd0,base_even}+(y+row)*stride+{20'd0,x,1'b0}) :
                  ({8'd0,(frame_line[0] ? base_odd : base_even)}+(frame_line>>1)*stride+x);
 wire [31:0] row_src={8'd0,source}+row*width;
 wire [12:0] row_dest_bytes=fill16 ? {width,1'b0} : {1'b0,width};
 always @(posedge clk)begin
  done<=0;
  if(reset)begin state<=IDLE;mem_req<=0;mem_burst<=1;error<=0;completions<=0;last_opcode<=0;end
  else if(!hold && error==0)begin
   if(start && state!=IDLE)error<=8'hb0;
   case(state)
    IDLE:if(start)begin
     if(descriptor>=32'h01000000 || descriptor[1:0]!=0)error<=8'hb1;
     else begin read_base<=descriptor;word_index<=0;command_phase<=0;state<=READ_REQ;end
    end
    READ_REQ:begin
     read_address<=read_base+{25'd0,word_index,2'b00};
     mem_req<=1;mem_we<=0;mem_burst<=1;mem_addr<=29'h06000000+((read_base+{25'd0,word_index,2'b00})>>3);mem_be<=8'hff;
     if(mem_req && mem_accept)begin mem_req<=0;state<=READ_WAIT;end
    end
    READ_WAIT:if(mem_rvalid)begin
     if(command_phase)words[word_index]<=be_word(mem_rdata,read_address[2]);
     else desc[word_index]<=be_word(mem_rdata,read_address[2]);
     if(word_index==(command_phase ? 14 : 9))state<=command_phase ? DECODE_CMD : DECODE_DESC;
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
     row<=0;
     if(words[0]!=32'h418f0000 && words[0]!=32'h01ac0000 && words[0]!=32'h00ac0000)error<=8'hb3;
     else if(words[7]>=32'h01000000 || words[8]>=32'h01000000 ||
       ({1'b0,words[12][10:0]}+{1'b0,words[13][10:0]}+1) > ({1'b0,words[11][10:0]}+1))error<=8'hb4;
     else if(words[0]==32'h00ac0000 && words[1]>=32'h01000000)error<=8'hb5;
     // The row buffer holds 128 words: copies up to 1017 pixels wide.
     else if(words[0]==32'h00ac0000 && words[13][10:0]>11'd1016)error<=8'hb7;
     else state<=ROW_START;
    end
    ROW_START:begin
     if(row_dest>=32'h01000000 || row_dest+row_dest_bytes>32'h01000000 ||
        (copy8 && (row_src>=32'h01000000 || row_src+width>32'h01000000)))error<=8'hb6;
     else begin
      dest_start<=row_dest[23:0];src_start<=row_src[23:0];dest_bytes<=row_dest_bytes;
      dest_words<=({10'd0,row_dest[2:0]}+row_dest_bytes+13'd7)>>3;
      src_words<=({10'd0,row_src[2:0]}+{1'b0,width}+13'd7)>>3;
      shift<=$signed({2'b00,row_src[2:0]})-$signed({2'b00,row_dest[2:0]});
      dest_index<=0;buf_fill<=0;
      state<=copy8 ? BURST_REQ : EMIT;
     end
    end
    BURST_REQ:begin
     // Up to 64 beats per request; the arbiter returns one beat per cycle of
     // DDRAM_DOUT_READY and keeps the read owned by the blitter until done.
     mem_req<=1;mem_we<=0;mem_be<=8'hff;
     mem_addr<=29'h06000000+{8'd0,src_start[23:3]}+{21'd0,buf_fill};
     mem_burst<=(src_words-buf_fill>8'd64) ? 8'd64 : src_words-buf_fill;
     if(mem_req && mem_accept)begin
      mem_req<=0;burst_left<=mem_burst;state<=BURST_WAIT;
     end
    end
    BURST_WAIT:if(mem_rvalid)begin
     buf_fill<=buf_fill+1'b1;burst_left<=burst_left-1'b1;
     if(burst_left==1)begin
      mem_burst<=1;
      if(buf_fill+1'b1==src_words)begin buf_raddr<=0;state<=PRIME;end
      else state<=BURST_REQ;
     end
    end
    PRIME:state<=PRIME_WAIT; // registered read of row_buf[0]
    PRIME_WAIT:begin
     // Low half of the first window: word 0 (unused when shift<0).
     lo_word<=buf_q;buf_raddr<=hi_index[6:0];state<=ROW_END;
    end
    ROW_END:state<=EMIT; // row_buf[buf_raddr] arrives in buf_q
    EMIT:begin
     mem_req<=1;mem_we<=1;mem_burst<=1;
     mem_addr<=29'h06000000+{8'd0,dest_start[23:3]}+{20'd0,dest_index};
     mem_wdata<=word_data;mem_be<=word_be;
     state<=WRITE_REQ;
    end
    WRITE_REQ:if(mem_req && mem_accept)begin
     mem_req<=0;
     if(dest_index+1'b1==dest_words)begin
      if(row+1'b1==height)begin done<=1;completions<=completions+1'b1;state<=IDLE;end
      else begin row<=row+1'b1;state<=ROW_START;end
     end else begin
      dest_index<=dest_index+1'b1;
      if(copy8)begin
       lo_word<=buf_q;buf_raddr<=hi_index[6:0]+7'd1;state<=ROW_END;
      end else state<=EMIT;
     end
    end
    default:error<=8'hbf;
   endcase
  end
 end
endmodule
