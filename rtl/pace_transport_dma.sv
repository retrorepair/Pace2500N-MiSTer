// SPDX-License-Identifier: GPL-3.0-only
// EMMA memory-to-transport DMA (channel 5): copies a block of guest memory into the section
// demultiplexer's transport input, as the boot loader's demux self-test (BFC0B118) drives it.
//  - B0009090 holds the physical address of a 40-byte descriptor; big-endian word 3 is the
//    first source byte and word 8 the last (inclusive) one.
//  - Writing B0009010 with bit 5 set starts the transfer; it is complete (B0009120 bit 5) once
//    every byte has left memory into the transport input buffer below.
//  - Input buffer: the transfer runs at memory speed into a 64-byte FIFO that the demux (or, in
//    video-ES mode, the MPEG decoder) drains at its own pace. The loader relies on this: its
//    32-byte flush (start, then B0009010 = 0 and the B0009130 acknowledge about 5 us later) must
//    be complete before that acknowledge, while the demux only takes the DMA input at the end
//    of the broadcast packet in progress (up to ~190 us). Without the buffer the completion
//    landed after the acknowledge and stayed pending into the loader's interrupt enable.
//    The depth is this model's choice (the EMMA's is not documented); 64 bytes covers the flush.
// Evidence: re/DEMUX_SELFTEST_PASSED.md. The genuine loader programs descriptor 00007D60 for
// 1FC1B188..1FC1B77B (1524 bytes of U202: six transport packets on PIDs 0 and 1, then zero
// fill) and later a 32-byte transfer from 1FC1B8F8; the self-test's expected buffers in U202
// (around 1B834) are exactly what the demux makes of those bytes. Descriptor chains, the other
// descriptor words and the other DMA channels are not used by this loader and are not modelled.
// Source decoding follows the CPU's own map (rtl/pace_firmware_cpu.sv): RAM below 16 MiB, the
// boot flash at 1FC00000 and the NOR window at 1F800000, both held in DDR at 0x32000000.
module pace_transport_dma(
 input wire clk,reset,hold,
 input wire start,
 input wire [31:0] descriptor,
 output reg done=0,
 output wire busy,                  // transferring, or input buffer not yet drained
 output wire mem_req,output wire [28:0] mem_addr,
 input wire mem_accept,mem_rvalid,input wire [63:0] mem_rdata,
 output wire out_valid,input wire out_ready,output wire [7:0] out_data
);
 localparam IDLE=0,FIRST=1,LAST=2,READ=3,SEND=4;
 reg [2:0] state=IDLE;
 reg waiting=0;              // a read was accepted; its beat has not arrived yet
 reg [28:0] address=0;       // physical address being read (descriptor word or source byte)
 reg [28:0] last=0;
 reg [63:0] beat=0;
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] fifo[0:63];
 reg [6:0] fifo_write=0,fifo_read=0;
 wire fifo_empty=fifo_write==fifo_read;
 wire fifo_full=fifo_write-fifo_read==7'd64;
 wire push=state==SEND && !hold && !fifo_full && !start && !reset;
 function automatic [28:0] ddr(input [28:0] physical);
  if(physical[28:24]==0)ddr=29'h06000000+{8'd0,physical[23:3]};
  else if((physical&29'h1fc00000)==29'h1fc00000)ddr=29'h06400000+{8'd0,physical[20:3]};
  else ddr=29'h06400000+{7'd0,physical[21:3]};  // 1F800000 NOR window (only other decoded source)
 endfunction
 // Big-endian 32-bit word at a 4-aligned byte offset within a 64-bit beat (byte n is in lane n).
 function automatic [31:0] word_at(input [63:0] b,input [2:0] offset);
  word_at=offset[2] ? {b[39:32],b[47:40],b[55:48],b[63:56]} : {b[7:0],b[15:8],b[23:16],b[31:24]};
 endfunction
 wire [31:0] word3=word_at(beat,address[2:0]^3'd4),word8=word_at(mem_rdata,address[2:0]);
 wire reading=state==FIRST || state==LAST || state==READ;
 assign busy=state!=IDLE || !fifo_empty;
 assign mem_req=reading && !waiting && !hold;
 assign mem_addr=ddr(address);
 assign out_valid=!fifo_empty && !hold;
 assign out_data=fifo[fifo_read[5:0]];
 always @(posedge clk)if(push)fifo[fifo_write[5:0]]<=beat[{address[2:0],3'b000}+:8];
 always @(posedge clk)begin
  if(!reset)begin
   if(push)fifo_write<=fifo_write+1'b1;
   if(out_valid && out_ready)fifo_read<=fifo_read+1'b1;
  end
  if(reset)begin state<=IDLE;waiting<=0;done<=0;fifo_write<=0;fifo_read<=0;end
  else if(start)begin
   // A new start (re)loads the descriptor; completion of the previous transfer is cleared.
   state<=FIRST;waiting<=0;done<=0;address<=descriptor[28:0]+29'd12;
  end else if(!hold)begin
   if(mem_req && mem_accept)waiting<=1;
   case(state)
    FIRST:if(mem_rvalid)begin waiting<=0;beat<=mem_rdata;state<=LAST;address<=address+29'd20;end
    LAST:if(mem_rvalid)begin
     waiting<=0;
     // address points at word 8 (descriptor+32); beat holds word 3 (descriptor+12, 20 bytes
     // earlier, so in the other half of its beat).
     address<=word3[28:0];
     last<=word8[28:0];
     state<=READ;
    end
    READ:if(mem_rvalid)begin waiting<=0;beat<=mem_rdata;state<=SEND;end
    SEND:if(!fifo_full)begin
     if(address==last)begin state<=IDLE;done<=1;end
     else begin
      address<=address+29'd1;
      if(address[2:0]==3'd7)state<=READ;
     end
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
