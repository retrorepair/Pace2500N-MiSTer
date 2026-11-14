// SPDX-License-Identifier: GPL-3.0-only
// Read the resident Sky Guide still from the loaded checkpoint. The original
// 720x576 MPEG-2 sequence is at guest RAM 0x00471300 in this firmware.
// Repeat the sequence so the streaming decoder can release its first reference
// picture for display, then leave the decoded still in its frame store.
module pace_guide_still(
 input wire clk,reset,enable,
 output wire mem_req,output wire [28:0] mem_addr,
 input wire mem_accept,mem_rvalid,input wire [63:0] mem_rdata,
 output wire [7:0] data,output wire valid,input wire ready,
 output reg present=0
);
 localparam [28:0] BASE=29'h0608e260;
 localparam [11:0] LAST_WORD=12'd2065; // 16524 bytes, four in the final word
 localparam IDLE=0,REQUEST=1,WAIT_DATA=2,OUTPUT=3,DONE=4;
 reg [2:0] state=IDLE,lane=0;
 reg [11:0] word_index=0;
 reg [1:0] repetition=0;
 reg [63:0] word_data=0;
 reg cancelled=0;
 assign mem_req=state==REQUEST && enable;
 assign mem_addr=BASE+{17'd0,word_index};
 assign data=word_data[lane*8+:8];
 assign valid=state==OUTPUT && enable;

 always @(posedge clk)begin
  if(reset)begin
   state<=IDLE;word_index<=0;repetition<=0;lane<=0;present<=0;cancelled<=0;
  end else if(state==WAIT_DATA)begin
   if(!enable)begin cancelled<=1;present<=0;end
   if(mem_rvalid)begin
    if(cancelled || !enable)state<=IDLE;
    else if(word_index==0 && mem_rdata!=64'h2440022db3010000)state<=DONE;
    else begin
     present<=1;word_data<=mem_rdata;lane<=0;state<=OUTPUT;
    end
   end
  end else if(!enable)begin
   state<=IDLE;word_index<=0;repetition<=0;lane<=0;present<=0;cancelled<=0;
  end else case(state)
   IDLE:begin word_index<=0;repetition<=0;cancelled<=0;state<=REQUEST;end
   REQUEST:if(mem_accept)state<=WAIT_DATA;
   OUTPUT:if(ready)begin
    if(word_index==LAST_WORD && lane==3)begin
     word_index<=0;repetition<=repetition+1'b1;
     state<=repetition==3 ? DONE : REQUEST;
    end else if(lane==7)begin
     word_index<=word_index+1'b1;state<=REQUEST;
    end else lane<=lane+1'b1;
   end
   default:begin end
  endcase
 end
endmodule
