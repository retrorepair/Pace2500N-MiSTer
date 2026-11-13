// SPDX-License-Identifier: GPL-3.0-only
// Functional application section-DMA profile, inferred from this ROM's driver.
// Not a cycle-accurate NEC demux or a PES/MPEG decoder. Repeats are dropped
// while completion is pending or the guest-programmed ring limit leaves
// insufficient room. No guest consumer pointers are poked by this module.
module pace_section_demux_ref(
 input wire clk,reset,hold,stream_reset,
 input wire ts_valid,output wire ts_ready,input wire [7:0] ts_data,
 input wire io_req,io_we,input wire [31:0] io_addr,io_wdata,
 input wire [1:0] io_size,output reg [31:0] io_rdata,
 output wire irq,config_ready,
 output wire mem_req,output wire [28:0] mem_addr,
 output wire [63:0] mem_wdata,output wire [7:0] mem_be,input wire mem_accept,
 output reg [31:0] packets=0,sections=0,dropped=0,crc_errors=0
);
 `include "rtl/pace_checkpoint_demux_match.vh"
 reg [31:0] pid_seed[0:31],ptr_seed[0:31],limit_seed[0:31];
 initial begin
  $readmemh("rom/checkpoint_demux_pid.hex",pid_seed);
  $readmemh("rom/checkpoint_demux_pointer.hex",ptr_seed);
  $readmemh("rom/checkpoint_demux_limit.hex",limit_seed);
 end
 reg [31:0] pids[0:31],pointers[0:31],limits[0:31];
 (* ramstyle="M10K" *) reg [31:0] match_words[0:255];
 initial $readmemh("rom/checkpoint_demux_match.hex",match_words);
 reg [7:0] match_address=0,init_index=0;
 reg [31:0] match_q=0,route_bitmap=0;
 reg init_active=1,init_seed=1;
 reg [31:0] status[0:3],enables[0:3];
 reg [31:0] control=32'h00100001,indirect_data=0,match_data=0;
 reg [4:0] selected=0;
 reg [12:0] used[0:31],total[0:31];
 reg [31:0] crc[0:31],signature[0:31];
 reg [3:0] last_cc[0:31];reg [31:0] cc_valid=0;
 reg [7:0] header[0:31][0:10];
 (* ramstyle="M10K" *) reg [7:0] section_ram[0:131071];
 reg [16:0] ram_read_address=0;reg [7:0] ram_q=0;
 reg [7:0] packet[0:187];reg [7:0] incoming=0,cursor=0,boundary=0;
 reg [31:0] packet_crc=32'hffffffff;
 reg [12:0] packet_pid=0;
 reg [7:0] payload=0;
 reg packet_bad=0,packet_discontinuity=0,packet_pusi=0,has_payload=0;
 reg [4:0] channel=0;reg new_allowed=0;
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
 // Guest evidence: channel22 route word 0x96 selects bit10 -> pair5 low
 // (TOT73); channel23 0x97 bit5 -> pair2 high (SDT42); channel24 0x98
 // bit3 -> pair1 high (NIT40). Title channel21 0x95 bit17 -> pair8 high.
 // There are 32 logical units, two per register pair, not 16 logical units.
 wire [15:0] rule_pair=unit[0]?match_q[31:16]:match_q[15:0];
 wire [3:0] header_index=rule_index==0?4'd0:rule_index+4'd2;
 wire [20:0] ring_base=channel*21'h03000;
 wire [20:0] write_within=pointers[channel]<{11'd0,ring_base} || pointers[channel]>={11'd0,ring_base}+32'h3000 ? 21'd0:pointers[channel][20:0]-ring_base;
 wire [20:0] limit_within=limits[channel][20:0]-ring_base;
 wire limit_valid=limits[channel]>={11'd0,ring_base} && limits[channel]<{11'd0,ring_base}+32'h3000;
 wire [20:0] ring_free=limit_within>=write_within ? limit_within-write_within : 21'h3000-write_within+limit_within;
 wire [20:0] record_size={8'd0,total[channel]}+21'd1;
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
   12'h128:io_rdata=pointers[selected]&32'h001fffff;
   12'h140:io_rdata=control;
   default:begin end
  endcase
  io_rdata=(io_rdata>>shift)&(io_size==0?32'hff:io_size==1?32'hffff:32'hffffffff);
 end
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
 always @(posedge clk)begin
  ram_q<=section_ram[ram_read_address];
  if(reset)begin
   state<=RX;incoming<=0;packet_crc<=32'hffffffff;cc_valid<=0;
   control<=32'h00100001;indirect_data<=0;match_data<=0;selected<=0;
   packets<=0;sections<=0;dropped<=0;crc_errors<=0;
   init_active<=1;init_seed<=1;init_index<=0;match_address<=0;
   for(i=0;i<32;i=i+1)begin pids[i]<=pid_seed[i];pointers[i]<=ptr_seed[i];limits[i]<=limit_seed[i];used[i]<=0;total[i]<=0;crc[i]<=32'hffffffff;end
   for(i=0;i<4;i=i+1)begin status[i]<=0;enables[i]<=i>=2?32'hffc00000:32'd0;end
  end else if(init_active)begin
   if(init_index==255)init_active<=0;
   else init_index<=init_index+1'b1;
  end else if(stream_reset)begin
   state<=RX;incoming<=0;packet_crc<=32'hffffffff;cc_valid<=0;
   for(i=0;i<32;i=i+1)used[i]<=0;
  end else if(!hold)begin
   case(state)
    RX:if(ts_valid)begin
     packet[incoming]<=ts_data;packet_crc<=crc_byte(packet_crc,ts_data);
     if(incoming==187)begin incoming<=0;state<=DECODE;packets<=packets+1'b1;end
     else incoming<=incoming+1'b1;
    end
    DECODE:begin
     packet_pid<={packet[1][4:0],packet[2]};packet_pusi<=packet[1][6];channel<=0;
     packet_bad<=packet[0]!=8'h47 || packet[1][7] || packet[3][7:6]!=0 || packet[3][5:4]==0 ||
                 (packet[3][5] && (packet[4]>183 || (packet[3][5:4]==2 && packet[4]!=183)));
     has_payload<=packet[3][4] && (!packet[3][5] || packet[4]<183);
     payload<=packet[3][5] ? 8'd5+packet[4] : 8'd4;
     packet_discontinuity<=packet[3][5] && packet[4]!=0 && packet[5][7];state<=CHANNEL;
    end
    CHANNEL:begin
     if(pids[channel][12:0]!=packet_pid || pids[channel][31:13]==0 || packet_pid==13'h1fff || !enables[2][channel] || !control[0])state<=NEXT_CHANNEL;
     else if(packet_bad)begin used[channel]<=0;cc_valid[channel]<=0;dropped<=dropped+1'b1;state<=NEXT_CHANNEL;end
     else if(!has_payload)begin
      if(packet_discontinuity)begin used[channel]<=0;cc_valid[channel]<=0;end
      state<=NEXT_CHANNEL;
     end else if(cc_valid[channel] && !packet_discontinuity && last_cc[channel]==packet[3][3:0] && signature[channel]==packet_crc)state<=NEXT_CHANNEL;
     else begin
      if(packet_discontinuity || (cc_valid[channel] && packet[3][3:0]!=(last_cc[channel]+4'd1)))used[channel]<=0;
      last_cc[channel]<=packet[3][3:0];signature[channel]<=packet_crc;cc_valid[channel]<=1;
      state<=BEGIN_PAYLOAD;
     end
    end
    BEGIN_PAYLOAD:begin
     new_allowed<=packet_pusi;boundary<=188;
     if(packet_pusi)begin
      if({1'b0,payload}+9'd1+{1'b0,packet[payload]}>188)begin used[channel]<=0;dropped<=dropped+1'b1;state<=NEXT_CHANNEL;end
      else begin cursor<=payload+1'b1;boundary<=payload+1'b1+packet[payload];state<=BYTE;end
     end else begin cursor<=payload;state<=BYTE;end
    end
    BYTE:begin
     // At the PUSI boundary, an unfinished previous section is invalid.
     if(cursor>=188)state<=NEXT_CHANNEL;
     else if(new_allowed && cursor==boundary)begin
      if(used[channel]!=0)dropped<=dropped+1'b1;
      used[channel]<=0;total[channel]<=0;crc[channel]<=32'hffffffff;boundary<=0;
     end else if(used[channel]==0 && (!new_allowed || cursor<boundary || current==8'hff))begin
      if(new_allowed && cursor<boundary)cursor<=boundary;
      else state<=NEXT_CHANNEL;
     end else begin
      section_ram[{channel,used[channel][11:0]}]<=current;
      if(used[channel]<11)header[channel][used[channel][3:0]]<=current;
      crc[channel]<=crc_byte(used[channel]==0?32'hffffffff:crc[channel],current);
      used[channel]<=used[channel]+1'b1;cursor<=cursor+1'b1;
      if(used[channel]==2)begin
       total[channel]<={1'b0,header[channel][1][3:0],current}+13'd3;
       if({1'b0,header[channel][1][3:0],current}>4093)begin used[channel]<=0;dropped<=dropped+1'b1;state<=NEXT_CHANNEL;end
       else if({header[channel][1][3:0],current}==0)state<=COMPLETE;
      end else if(used[channel]>=3 && used[channel]+1'b1==total[channel])state<=COMPLETE;
     end
    end
    COMPLETE:begin
     if((header[channel][1][7] || header[channel][0]==8'h73) && (total[channel]<7 || crc[channel]!=0))begin
      crc_errors<=crc_errors+1'b1;used[channel]<=0;state<=BYTE;
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
     if((header[channel][header_index]&rule_pair[7:0])!=(rule_pair[15:8]&rule_pair[7:0]) ||
       (rule_pair[7:0]!=0 && {9'd0,header_index}>=total[channel]))unit_ok<=0;
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
      dropped<=dropped+1'b1;used[channel]<=0;state<=BYTE;
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
      if(dma_index==total[channel])begin
       pointers[channel]<={11'd0,ring_base}+{18'd0,dma_following};
       status[2][channel]<=1;sections<=sections+1'b1;used[channel]<=0;state<=BYTE;
      end else begin dma_index<=dma_index+1'b1;dma_position<=dma_following;state<=DMA_ADDRESS;end
     end
    end
    NEXT_CHANNEL:begin
     if(channel==31)begin state<=RX;packet_crc<=32'hffffffff;end
     else begin channel<=channel+1'b1;state<=CHANNEL;end
    end
    default:state<=RX;
   endcase
   if(io_req && io_we && config_ready)begin
    case(off)
     12'h0b0,12'h0b4,12'h0b8,12'h0bc:status[off[3:2]]<=status[off[3:2]]&(~lane_mask|lane_bits);
     12'h0d0,12'h0d4,12'h0d8,12'h0dc:enables[off[3:2]]<=enables[off[3:2]]|lane_bits;
     12'h124:begin
      selected<=io_wdata[6:2];
      if(io_wdata[15:14]==2'b11)case(io_wdata[1:0])
       0:pointers[io_wdata[6:2]]<=indirect_data&32'h001fffff;
       2:limits[io_wdata[6:2]]<=indirect_data&32'h001fffff;
       default:begin end
      endcase
     end
     12'h128:indirect_data<=io_wdata;
     12'h140:control<=io_wdata;
     12'h148:match_data<=io_wdata;
     12'h000:if(io_wdata[0])begin
      for(j=0;j<4;j=j+1)begin status[j]<=0;enables[j]<=0;end
      for(j=0;j<32;j=j+1)begin pids[j]<=0;used[j]<=0;pointers[j]<=0;limits[j]<=0;end
      init_active<=1;init_seed<=0;init_index<=0;
      control<=0;state<=RX;incoming<=0;cc_valid<=0;packet_crc<=32'hffffffff;
     end
     default:if(off>=12'h014 && off<12'h094)begin
      pids[reg_channel]<=io_wdata;used[reg_channel]<=0;cc_valid[reg_channel]<=0;
     end
    endcase
    // A simultaneous DMA completion must survive a guest clear of an older
    // status word; payload/pointer publication always precedes its interrupt.
    if(state==DMA_WRITE && mem_accept && dma_index==total[channel] && !(off==0 && io_wdata[0]))status[2][channel]<=1;
   end
  end
 end
 always @* dma_byte=dma_index==total[channel]?8'd0:ram_q;
endmodule
