// SPDX-License-Identifier: GPL-3.0-only
// Functional application section-DMA profile, inferred from this ROM's driver.
// Not a cycle-accurate NEC demux or a PES/MPEG decoder. Sections keep
// filling a channel's ring while its interrupt is pending; one is dropped
// only when the guest-programmed ring limit leaves insufficient room.
// No guest consumer pointers are poked by this module.
//
// Storage: every per-channel table and the packet buffer has exactly one
// write port and is read asynchronously, so each maps to MLAB memory while
// keeping the read-after-write timing of the flip-flop arrays it replaces
// (written on a clock edge, readable in the very next cycle). Whole-table
// clears are 32-bit flag vectors instead of 32 parallel writes:
//  - pids/pointers/limits: *_written[i]=0 reads the reset value (checkpoint
//    seed after a hard reset, zero after the guest's soft reset).
//  - used: used_fresh[i]=1 reads zero.
//  - pointers have two writers (section completion and the guest's indirect
//    write), so they use two banks and a per-channel "latest bank" bit.
// total/crc/signature/last_cc/header need no clear: each is only read after
// the state machine has rewritten it for the current section/packet.
// sim/baseline_demux holds the original flip-flop version; build with
// +define+PACE_DEMUX_LOCKSTEP to run it alongside and compare every output.
module pace_section_demux(
 input wire clk,reset,hold,stream_reset,
 input wire ts_valid,output wire ts_ready,input wire [7:0] ts_data,
 input wire io_req,io_we,input wire [31:0] io_addr,io_wdata,
 input wire [1:0] io_size,output reg [31:0] io_rdata,
 output wire irq,config_ready,
 output wire mem_req,output wire [28:0] mem_addr,
 output wire [63:0] mem_wdata,output wire [7:0] mem_be,input wire mem_accept,
 output reg [31:0] packets=0,sections=0,dropped=0,crc_errors=0,
 // A/V PES channels as programmed by the firmware (hardware trace 10 Nov 2026):
 // B000A094 video, B000A098 audio: [12:0] PID, bit 14 enable; B000A010 PCR PID.
 output reg [15:0] av_video=16'h1fff,av_audio=16'h1fff,av_pcr=16'h1fff
);
 `include "rtl/pace_checkpoint_demux_match.vh"
 reg [31:0] pid_seed[0:31],ptr_seed[0:31],limit_seed[0:31];
 initial begin
  $readmemh("rom/checkpoint_demux_pid.hex",pid_seed);
  $readmemh("rom/checkpoint_demux_pointer.hex",ptr_seed);
  $readmemh("rom/checkpoint_demux_limit.hex",limit_seed);
 end
 (* ramstyle="M10K" *) reg [31:0] match_words[0:255];
 initial $readmemh("rom/checkpoint_demux_match.hex",match_words);
 reg [7:0] match_address=0,init_index=0;
 reg [31:0] match_q=0,route_bitmap=0;
 reg init_active=1,init_seed=1;
 reg [31:0] status[0:3],enables[0:3];
 reg [31:0] control=32'h00100001,indirect_data=0,match_data=0;
 reg [4:0] selected=0;
 reg [4:0] channel=0;reg new_allowed=0;
 // ---- Per-channel tables (MLAB, one write port, asynchronous read).
 reg seeded=1;  // reset values are the checkpoint seeds (1) or zero (0)
 // PID filter: only pid[12:0] and pid[31:13]!=0 are used.
 (* ramstyle="MLAB, no_rw_check" *) reg [13:0] pid_mem[0:31];
 reg [31:0] pid_written=0;
 // Producer pointers (bank a: section completion, bank b: guest write) and
 // ring limits. Written values are always masked to 21 bits.
 (* ramstyle="MLAB, no_rw_check" *) reg [20:0] ptr_a[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [20:0] ptr_b[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [20:0] lim_mem[0:31];
 reg [31:0] ptr_written=0,ptr_bank=0,lim_written=0;
 (* ramstyle="MLAB, no_rw_check" *) reg [12:0] used_mem[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [12:0] total_mem[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [31:0] crc_mem[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [35:0] sig_mem[0:31];  // {last_cc,signature}
 reg [31:0] used_fresh=32'hffffffff;
 reg [31:0] cc_valid=0;
 // Section header bytes the filters and length logic read (2 and 10 never are).
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] hdr0[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] hdr1[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] hdr3[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] hdr4[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] hdr5[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] hdr6[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] hdr7[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] hdr8[0:31];
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] hdr9[0:31];
 // Current-channel views.
 wire [31:0] pid_seed_c=pid_seed[channel];
 wire [13:0] pid_c=pid_written[channel] ? pid_mem[channel] :
                   seeded ? {pid_seed_c[31:13]!=0,pid_seed_c[12:0]} : 14'd0;
 wire [31:0] pointer_c=ptr_written[channel] ? {11'd0,ptr_bank[channel] ? ptr_b[channel] : ptr_a[channel]} :
                       seeded ? ptr_seed[channel] : 32'd0;
 wire [31:0] pointer_sel=ptr_written[selected] ? {11'd0,ptr_bank[selected] ? ptr_b[selected] : ptr_a[selected]} :
                         seeded ? ptr_seed[selected] : 32'd0;
 wire [31:0] limit_c=lim_written[channel] ? {11'd0,lim_mem[channel]} :
                     seeded ? limit_seed[channel] : 32'd0;
 wire [12:0] used_c=used_fresh[channel] ? 13'd0 : used_mem[channel];
 wire [12:0] total_c=total_mem[channel];
 wire [31:0] crc_c=crc_mem[channel];
 wire [35:0] sig_c=sig_mem[channel];
 wire [3:0] last_cc_c=sig_c[35:32];
 wire [31:0] signature_c=sig_c[31:0];
 wire [7:0] hdr0_c=hdr0[channel],hdr1_c=hdr1[channel];
 (* ramstyle="M10K" *) reg [7:0] section_ram[0:131071];
 reg [16:0] ram_read_address=0;reg [7:0] ram_q=0;
 // Packet buffer; bytes 0-5 also kept in registers for the header decode.
 (* ramstyle="MLAB, no_rw_check" *) reg [7:0] packet[0:187];
 reg [7:0] pk0=0,pk1=0,pk2=0,pk3=0,pk4=0,pk5=0;
 reg [7:0] incoming=0,cursor=0,boundary=0;
 reg [31:0] packet_crc=32'hffffffff;
 reg [12:0] packet_pid=0;
 reg [7:0] payload=0;
 reg packet_bad=0,packet_discontinuity=0,packet_pusi=0,has_payload=0;
 reg [4:0] unit=0;reg [3:0] rule_index=0;
 reg unit_ok=0,any_match=0;
 reg [13:0] dma_position=0;reg [12:0] dma_index=0;
 reg [7:0] dma_byte=0;
 localparam RX=0,DECODE=1,CHANNEL=2,BEGIN_PAYLOAD=3,BYTE=4,COMPLETE=5,
            MATCH_START=6,MATCH_BYTE=7,MATCH_NEXT=8,DECIDE=9,
            DMA_ADDRESS=10,DMA_CAPTURE=11,DMA_WRITE=12,NEXT_CHANNEL=13,
            ROUTE_WAIT=14,ROUTE_LATCH=15,RULE_WAIT=16;
 reg [4:0] state=RX;
 function automatic [31:0] crc_byte(input [31:0] old_crc,input[7:0] value);
  reg [31:0] c;integer b;
  begin c=old_crc^{value,24'd0};for(b=0;b<8;b=b+1)c=c[31]?(c<<1)^32'h04c11db7:c<<1;crc_byte=c;end
 endfunction
 wire [7:0] current=packet[cursor];
 wire [7:0] pointer_field=packet[payload];
 // Guest evidence: channel22 route word 0x96 selects bit10 -> pair5 low
 // (TOT73); channel23 0x97 bit5 -> pair2 high (SDT42); channel24 0x98
 // bit3 -> pair1 high (NIT40). Title channel21 0x95 bit17 -> pair8 high.
 // There are 32 logical units, two per register pair, not 16 logical units.
 wire [15:0] rule_pair=unit[0]?match_q[31:16]:match_q[15:0];
 wire [3:0] header_index=rule_index==0?4'd0:rule_index+4'd2;
 reg [7:0] header_byte;
 always @* case(header_index)
  4'd0:header_byte=hdr0_c;4'd3:header_byte=hdr3[channel];4'd4:header_byte=hdr4[channel];
  4'd5:header_byte=hdr5[channel];4'd6:header_byte=hdr6[channel];4'd7:header_byte=hdr7[channel];
  4'd8:header_byte=hdr8[channel];4'd9:header_byte=hdr9[channel];
  default:header_byte=8'd0; // header_index is 0 or 3..9
 endcase
 wire [20:0] ring_base=channel*21'h03000;
 wire [20:0] write_within=pointer_c<{11'd0,ring_base} || pointer_c>={11'd0,ring_base}+32'h3000 ? 21'd0:pointer_c[20:0]-ring_base;
 wire [20:0] limit_within=limit_c[20:0]-ring_base;
 wire limit_valid=limit_c>={11'd0,ring_base} && limit_c<{11'd0,ring_base}+32'h3000;
 wire [20:0] ring_free=limit_within>=write_within ? limit_within-write_within : 21'h3000-write_within+limit_within;
 wire [20:0] record_size={8'd0,total_c}+21'd1;
 wire [13:0] dma_following=dma_position==14'h2fff ? 14'd0 : dma_position+14'd1;
 wire [23:0] physical=24'h7a0000+{3'd0,ring_base}+{10'd0,dma_position};
 wire [11:0] off={io_addr[11:2],2'b00};
 wire [4:0] reg_channel=5'((off-12'h014)>>2);
 wire [4:0] shift=io_size==0?{(2'd3-io_addr[1:0]),3'b000}:io_size==1?{io_addr[1]?2'd0:2'd2,3'b000}:5'd0;
 wire [31:0] lane_mask=(io_size==0?32'hff:io_size==1?32'hffff:32'hffffffff)<<shift;
 wire [31:0] lane_bits=(io_wdata<<shift)&lane_mask;
 assign config_ready=!init_active;
 assign irq=(status[2]&enables[2])!=0;
 assign ts_ready=state==RX && !hold && config_ready;
 assign mem_req=state==DMA_WRITE && !hold;
 assign mem_addr=29'h06000000+{8'd0,physical[23:3]};
 assign mem_wdata={56'd0,dma_byte}<<(physical[2:0]*8);
 assign mem_be=8'h01<<physical[2:0];
 always @* begin
  io_rdata=0;
  case(off)
   12'h0b0,12'h0b4,12'h0b8,12'h0bc:io_rdata=status[off[3:2]];
   12'h0d0,12'h0d4,12'h0d8,12'h0dc:io_rdata=enables[off[3:2]];
   12'h128:io_rdata=pointer_sel&32'h001fffff;
   12'h094:io_rdata={16'd0,av_video};
   12'h098:io_rdata={16'd0,av_audio};
   12'h010:io_rdata={16'd0,av_pcr};
   12'h140:io_rdata=control;
   default:begin end
  endcase
  io_rdata=(io_rdata>>shift)&(io_size==0?32'hff:io_size==1?32'hffff:32'hffffffff);
 end
 // ---- Write ports. The state machine below sets these (blocking) and the
 // single write per table happens at the end of the clocked block.
 reg used_we,total_we,crc_we,sig_we,ptr_a_we;
 reg [12:0] used_wd,total_wd;reg [31:0] crc_wd;reg [35:0] sig_wd;reg [20:0] ptr_a_wd;
 reg cpu_we,pid_we,ptr_b_we,lim_we;
 reg [4:0] cpu_index;
 integer i,j;
 // One synchronous read port and one write port infer a single M10K instead
 // of thousands of flip-flops plus a global combinational mux. Reset/clear
 // walks the table while config_ready is low; normal CPU writes then resume.
 always @(posedge clk)begin
  match_q<=match_words[match_address];
  if(!reset)begin
   if(init_active)match_words[init_index]<=init_seed?match_seed_word(init_index):32'd0;
   else if(!hold && io_req && io_we && off==12'h144 && io_wdata[15:14]==2'b11)
    match_words[{io_wdata[3:0],io_wdata[7:4]}]<=match_data;
  end
 end
 // Guest register writes to the per-channel tables. One port per table,
 // indexed by the register being written.
 always @* begin
  cpu_we=!reset && !init_active && !stream_reset && !hold && io_req && io_we && config_ready;
  pid_we=cpu_we && off>=12'h014 && off<12'h094;
  ptr_b_we=cpu_we && off==12'h124 && io_wdata[15:14]==2'b11 && io_wdata[1:0]==2'd0;
  lim_we=cpu_we && off==12'h124 && io_wdata[15:14]==2'b11 && io_wdata[1:0]==2'd2;
  cpu_index=pid_we ? reg_channel : io_wdata[6:2];
 end
 always @(posedge clk)begin
  if(pid_we)pid_mem[cpu_index]<={io_wdata[31:13]!=0,io_wdata[12:0]};
  if(ptr_b_we)ptr_b[cpu_index]<=indirect_data[20:0];
  if(lim_we)lim_mem[cpu_index]<=indirect_data[20:0];
 end
 always @(posedge clk)begin
  ram_q<=section_ram[ram_read_address];
  used_we=0;total_we=0;crc_we=0;sig_we=0;ptr_a_we=0;
  used_wd=0;total_wd=0;crc_wd=0;sig_wd=0;ptr_a_wd=0;
  if(reset)begin
   state<=RX;incoming<=0;packet_crc<=32'hffffffff;cc_valid<=0;
   control<=32'h00100001;indirect_data<=0;match_data<=0;selected<=0;
   packets<=0;sections<=0;dropped<=0;crc_errors<=0;
   init_active<=1;init_seed<=1;init_index<=0;match_address<=0;
   av_video<=16'h1fff;av_audio<=16'h1fff;av_pcr<=16'h1fff;
   seeded<=1;pid_written<=0;ptr_written<=0;ptr_bank<=0;lim_written<=0;used_fresh<=32'hffffffff;
   for(i=0;i<4;i=i+1)begin status[i]<=0;enables[i]<=i>=2?32'hffc00000:32'd0;end
  end else if(init_active)begin
   if(init_index==255)init_active<=0;
   else init_index<=init_index+1'b1;
  end else if(stream_reset)begin
   state<=RX;incoming<=0;packet_crc<=32'hffffffff;cc_valid<=0;
   used_fresh<=32'hffffffff;
  end else if(!hold)begin
   case(state)
    RX:if(ts_valid)begin
     packet[incoming]<=ts_data;packet_crc<=crc_byte(packet_crc,ts_data);
     case(incoming)
      8'd0:pk0<=ts_data;8'd1:pk1<=ts_data;8'd2:pk2<=ts_data;
      8'd3:pk3<=ts_data;8'd4:pk4<=ts_data;8'd5:pk5<=ts_data;
      default:begin end
     endcase
     if(incoming==187)begin incoming<=0;state<=DECODE;packets<=packets+1'b1;end
     else incoming<=incoming+1'b1;
    end
    DECODE:begin
     packet_pid<={pk1[4:0],pk2};packet_pusi<=pk1[6];channel<=0;
     packet_bad<=pk0!=8'h47 || pk1[7] || pk3[7:6]!=0 || pk3[5:4]==0 ||
                 (pk3[5] && (pk4>183 || (pk3[5:4]==2 && pk4!=183)));
     has_payload<=pk3[4] && (!pk3[5] || pk4<183);
     payload<=pk3[5] ? 8'd5+pk4 : 8'd4;
     packet_discontinuity<=pk3[5] && pk4!=0 && pk5[7];state<=CHANNEL;
    end
    CHANNEL:begin
     if(pid_c[12:0]!=packet_pid || !pid_c[13] || packet_pid==13'h1fff || !enables[2][channel] || !control[0])state<=NEXT_CHANNEL;
     else if(packet_bad)begin used_we=1;used_wd=0;cc_valid[channel]<=0;dropped<=dropped+1'b1;state<=NEXT_CHANNEL;end
     else if(!has_payload)begin
      if(packet_discontinuity)begin used_we=1;used_wd=0;cc_valid[channel]<=0;end
      state<=NEXT_CHANNEL;
     end else if(cc_valid[channel] && !packet_discontinuity && last_cc_c==pk3[3:0] && signature_c==packet_crc)state<=NEXT_CHANNEL;
     else begin
      if(packet_discontinuity || (cc_valid[channel] && pk3[3:0]!=(last_cc_c+4'd1)))begin used_we=1;used_wd=0;end
      sig_we=1;sig_wd={pk3[3:0],packet_crc};cc_valid[channel]<=1;
      state<=BEGIN_PAYLOAD;
     end
    end
    BEGIN_PAYLOAD:begin
     new_allowed<=packet_pusi;boundary<=188;
     if(packet_pusi)begin
      if({1'b0,payload}+9'd1+{1'b0,pointer_field}>188)begin used_we=1;used_wd=0;dropped<=dropped+1'b1;state<=NEXT_CHANNEL;end
      else begin cursor<=payload+1'b1;boundary<=payload+1'b1+pointer_field;state<=BYTE;end
     end else begin cursor<=payload;state<=BYTE;end
    end
    BYTE:begin
     // At the PUSI boundary, an unfinished previous section is invalid.
     if(cursor>=188)state<=NEXT_CHANNEL;
     else if(new_allowed && cursor==boundary)begin
      if(used_c!=0)dropped<=dropped+1'b1;
      used_we=1;used_wd=0;total_we=1;total_wd=0;crc_we=1;crc_wd=32'hffffffff;boundary<=0;
     end else if(used_c==0 && (!new_allowed || cursor<boundary || current==8'hff))begin
      if(new_allowed && cursor<boundary)cursor<=boundary;
      else state<=NEXT_CHANNEL;
     end else begin
      section_ram[{channel,used_c[11:0]}]<=current;
      case(used_c)
       13'd0:hdr0[channel]<=current;13'd1:hdr1[channel]<=current;13'd3:hdr3[channel]<=current;
       13'd4:hdr4[channel]<=current;13'd5:hdr5[channel]<=current;13'd6:hdr6[channel]<=current;
       13'd7:hdr7[channel]<=current;13'd8:hdr8[channel]<=current;13'd9:hdr9[channel]<=current;
       default:begin end
      endcase
      crc_we=1;crc_wd=crc_byte(used_c==0?32'hffffffff:crc_c,current);
      used_we=1;used_wd=used_c+1'b1;cursor<=cursor+1'b1;
      if(used_c==2)begin
       total_we=1;total_wd={1'b0,hdr1_c[3:0],current}+13'd3;
       if({1'b0,hdr1_c[3:0],current}>4093)begin used_wd=0;dropped<=dropped+1'b1;state<=NEXT_CHANNEL;end
       else if({hdr1_c[3:0],current}==0)state<=COMPLETE;
      end else if(used_c>=3 && used_c+1'b1==total_c)state<=COMPLETE;
     end
    end
    COMPLETE:begin
     if((hdr1_c[7] || hdr0_c==8'h73) && (total_c<7 || crc_c!=0))begin
      crc_errors<=crc_errors+1'b1;used_we=1;used_wd=0;state<=BYTE;
     end else begin
      match_address<={channel[3:0],(channel[4]?4'd9:4'd8)};
      state<=ROUTE_WAIT;
     end
    end
    ROUTE_WAIT:state<=ROUTE_LATCH;
    ROUTE_LATCH:begin route_bitmap<=match_q;unit<=0;any_match<=0;state<=MATCH_START;end
    MATCH_START:begin
     unit_ok<=1;rule_index<=0;
     if(route_bitmap[unit])begin match_address<={unit[4:1],4'd0};state<=RULE_WAIT;end
     else state<=MATCH_NEXT;
    end
    RULE_WAIT:state<=MATCH_BYTE;
    MATCH_BYTE:begin
     if((header_byte&rule_pair[7:0])!=(rule_pair[15:8]&rule_pair[7:0]) ||
       (rule_pair[7:0]!=0 && {9'd0,header_index}>=total_c))unit_ok<=0;
     if(rule_index==7)state<=MATCH_NEXT;
     else begin rule_index<=rule_index+1'b1;match_address<={unit[4:1],(rule_index+4'd1)};state<=RULE_WAIT;end
    end
    MATCH_NEXT:begin
     if(route_bitmap[unit] && unit_ok)any_match<=1;
     if(unit==31)state<=DECIDE;else begin unit<=unit+1'b1;state<=MATCH_START;end
    end
    DECIDE:begin
     // A pending completion does not stop the next section: the firmware's
     // section task (80004520) consumes every record up to the published
     // write pointer per wake-up and bounds the ring with its limit
     // (consumer-32), so only a full ring drops a section.
     if(!any_match || !limit_valid || record_size>ring_free)begin
      dropped<=dropped+1'b1;used_we=1;used_wd=0;state<=BYTE;
     end else begin
      dma_position<=write_within[13:0];
      dma_index<=0;state<=DMA_ADDRESS;
     end
    end
    DMA_ADDRESS:begin ram_read_address<={channel,dma_index[11:0]};state<=DMA_CAPTURE;end
    DMA_CAPTURE:begin state<=DMA_WRITE;end
    DMA_WRITE:begin
     // ram_q is registered; it has settled before request acceptance.
     if(mem_accept)begin
      if(dma_index==total_c)begin
       ptr_a_we=1;ptr_a_wd=ring_base+{7'd0,dma_following};
       status[2][channel]<=1;sections<=sections+1'b1;used_we=1;used_wd=0;state<=BYTE;
      end else begin dma_index<=dma_index+1'b1;dma_position<=dma_following;state<=DMA_ADDRESS;end
     end
    end
    NEXT_CHANNEL:begin
     if(channel==31)begin state<=RX;packet_crc<=32'hffffffff;end
     else begin channel<=channel+1'b1;state<=CHANNEL;end
    end
    default:state<=RX;
   endcase
   // State-machine table writes (all at the current channel).
   if(used_we)begin used_mem[channel]<=used_wd;used_fresh[channel]<=0;end
   if(total_we)total_mem[channel]<=total_wd;
   if(crc_we)crc_mem[channel]<=crc_wd;
   if(sig_we)sig_mem[channel]<=sig_wd;
   if(ptr_a_we)begin ptr_a[channel]<=ptr_a_wd;ptr_written[channel]<=1;ptr_bank[channel]<=0;end
   if(io_req && io_we && config_ready)begin
    case(off)
     12'h0b0,12'h0b4,12'h0b8,12'h0bc:status[off[3:2]]<=status[off[3:2]]&(~lane_mask|lane_bits);
     12'h0d0,12'h0d4,12'h0d8,12'h0dc:enables[off[3:2]]<=enables[off[3:2]]|lane_bits;
     12'h124:begin
      selected<=io_wdata[6:2];
      if(io_wdata[15:14]==2'b11)case(io_wdata[1:0])
       0:begin ptr_written[io_wdata[6:2]]<=1;ptr_bank[io_wdata[6:2]]<=1;end // ptr_b write
       2:lim_written[io_wdata[6:2]]<=1;                                     // lim_mem write
       default:begin end
      endcase
     end
     12'h128:indirect_data<=io_wdata;
     12'h094:av_video<=io_wdata[15:0];
     12'h098:av_audio<=io_wdata[15:0];
     12'h010:av_pcr<=io_wdata[15:0];
     12'h140:control<=io_wdata;
     12'h148:match_data<=io_wdata;
     12'h000:if(io_wdata[0])begin
      for(j=0;j<4;j=j+1)begin status[j]<=0;enables[j]<=0;end
      av_video<=16'h1fff;av_audio<=16'h1fff;av_pcr<=16'h1fff;
      seeded<=0;pid_written<=0;ptr_written<=0;lim_written<=0;used_fresh<=32'hffffffff;
      init_active<=1;init_seed<=0;init_index<=0;
      control<=0;state<=RX;incoming<=0;cc_valid<=0;packet_crc<=32'hffffffff;
     end
     default:if(off>=12'h014 && off<12'h094)begin
      pid_written[reg_channel]<=1;used_fresh[reg_channel]<=1;cc_valid[reg_channel]<=0; // pid_mem write
     end
    endcase
    // A simultaneous DMA completion must survive a guest clear of an older
    // status word; payload/pointer publication always precedes its interrupt.
    if(state==DMA_WRITE && mem_accept && dma_index==total_c && !(off==0 && io_wdata[0]))status[2][channel]<=1;
   end
  end
 end
 always @* dma_byte=dma_index==total_c?8'd0:ram_q;
 // synthesis translate_off
 // Effective table contents, for testbench checks.
 reg [31:0] pids[0:31],pointers[0:31];
 integer k;
 always @* for(k=0;k<32;k=k+1)begin
  pids[k]=pid_written[k] ? {18'd0,pid_mem[k]} : seeded ? pid_seed[k] : 32'd0;
  pointers[k]=ptr_written[k] ? {11'd0,ptr_bank[k] ? ptr_b[k] : ptr_a[k]} : seeded ? ptr_seed[k] : 32'd0;
 end
`ifdef PACE_DEMUX_LOCKSTEP
 // The original flip-flop implementation, driven identically; every output
 // must match on every cycle.
 wire ref_ts_ready,ref_irq,ref_config_ready,ref_mem_req;wire [31:0] ref_io_rdata;
 wire [28:0] ref_mem_addr;wire [63:0] ref_mem_wdata;wire [7:0] ref_mem_be;
 wire [31:0] ref_packets,ref_sections,ref_dropped,ref_crc_errors;
 pace_section_demux_ref golden(.clk(clk),.reset(reset),.hold(hold),.stream_reset(stream_reset),
  .ts_valid(ts_valid),.ts_ready(ref_ts_ready),.ts_data(ts_data),
  .io_req(io_req),.io_we(io_we),.io_addr(io_addr),.io_wdata(io_wdata),.io_size(io_size),.io_rdata(ref_io_rdata),
  .irq(ref_irq),.config_ready(ref_config_ready),.mem_req(ref_mem_req),.mem_addr(ref_mem_addr),
  .mem_wdata(ref_mem_wdata),.mem_be(ref_mem_be),.mem_accept(mem_accept),
  .packets(ref_packets),.sections(ref_sections),.dropped(ref_dropped),.crc_errors(ref_crc_errors));
 reg [63:0] lockstep_cycles=0;
 always @(negedge clk)begin
  lockstep_cycles<=lockstep_cycles+1;
  if(ref_ts_ready!==ts_ready || ref_irq!==irq || ref_config_ready!==config_ready || ref_mem_req!==mem_req ||
     ref_io_rdata!==io_rdata || ref_packets!==packets || ref_sections!==sections || ref_dropped!==dropped ||
     ref_crc_errors!==crc_errors || golden.state!==state ||
     (mem_req && (ref_mem_addr!==mem_addr || ref_mem_wdata!==mem_wdata || ref_mem_be!==mem_be)))
   $fatal(1,"demux lockstep mismatch at %0d: state %0d/%0d io_rdata %h/%h packets %0d/%0d sections %0d/%0d dropped %0d/%0d",
    lockstep_cycles,state,golden.state,io_rdata,ref_io_rdata,packets,ref_packets,sections,ref_sections,dropped,ref_dropped);
 end
`endif
 // synthesis translate_on
endmodule
