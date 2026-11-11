// SPDX-License-Identifier: GPL-3.0-only
// Streams a transport-stream file of any length from a MiSTer-mounted image
// (hps_io block interface, 512-byte blocks) into a DDR3 ring buffer that
// pace_ts_replay plays out at the broadcast rate. The file is read ahead of
// the player in 8 KiB requests and loops at its end, so a channel's stream can
// be as long as the file on the server share.
//
// Joining at "now": a stream file may begin with a Pace stream-info packet
// (PID 0x1FFE, payload "PACESTRM" + the UTC second of the day at which file
// byte 0 is on air, big-endian u32). The file is a constant-rate mux at
// RATE bytes per second that repeats back to back, so the byte on air now is
// ((now - anchor) * RATE) mod size (a signed modulo: the same day-relative
// layout the EPG uses, tools/pace_si.py loop_events), rounded down to 24,064 bytes (128 packets,
// 47 blocks: block- and packet-aligned). Without the packet, or before the
// clock is known, the stream starts at byte 0.
//
// Live mode (a "PACELIVE" header): the image is a ring file kept in RAM on
// the HPS by tools/mister/pace_live_relay.py, which fills it on demand from
// the PC playout server. Layout (all fields big-endian):
//   block 0  header, written by the relay:
//            47 1F FE 10 "PACELIVE" session(u32) written(u32) ring_bytes(u32)
//            `written` = bytes of this session placed in the ring so far, a
//            multiple of CHUNK; ring_bytes = power of two >= 64 KiB.
//   block 1  status, written by the core (sd_wr): "PACESTAT" session(u32)
//            read_pos(u32) video_pid(u16) audio_pid(u16) seq(u32)
//            played(u32) underruns(u32)  (the PIDs are the firmware's demux
//            A/V routing registers, B000A094/B000A098, which is how the
//            receiver "tunes": the relay asks the PC for that service)
//   block 2+ ring data: session byte n is at 1024 + (n mod ring_bytes).
// The core re-reads the header and writes its status every POLL_MAX clocks
// (sooner when it has caught up with the relay). A new session (the PC
// started a different stream) restarts playback at the next TS packet
// boundary of the outgoing stream, so the demux never sees a torn packet;
// if the player is stalled mid-packet it restarts after SWITCH_WAIT with a
// demux resynchronisation instead.
//
// Ring: RING_BYTES (power of two) at BASE. `written` and the player's `played`
// are free-running byte counters; the player may only consume bytes below
// `written`, and the reader only fetches while the ring has room for a whole
// request ahead of `played`.
module pace_ts_stream #(
 parameter [28:0] BASE=29'h06600000,      // DDR word address (HPS 0x33000000)
 parameter integer RING_BITS=22,           // 4 MiB ring
 parameter integer RATE=781250,            // bytes per second (6.25 Mbit/s replay)
 parameter integer POLL_MAX=2500000,       // live: header/status at least every 50 ms
 parameter integer POLL_MIN=250000,        // live: at most every 5 ms while waiting for data
 parameter integer SWITCH_WAIT=5000000     // live: 100 ms for a packet boundary
)(
 input wire clk,reset,
 input wire [16:0] now_seconds,input wire now_valid,   // UTC second of the day (broadcast clock)
 // hps_io image slot 0
 input wire img_mounted,input wire [63:0] img_size,
 output reg [31:0] sd_lba=0,output reg [5:0] sd_blk_cnt=0,output reg sd_rd=0,output reg sd_wr=0,
 input wire sd_ack,input wire [12:0] sd_buff_addr,input wire [15:0] sd_buff_dout,input wire sd_buff_wr,
 output reg [15:0] sd_buff_din=0,
 // live mode: status reported to the relay, and the player's packet phase
 input wire [15:0] video_pid,audio_pid,input wire [31:0] underruns,
 input wire boundary,                // the player is between two TS packets
 // player position (bytes consumed since the stream started)
 input wire [31:0] played,
 output reg active=0,               // a stream file is mounted
 output reg restart=0,              // one-cycle pulse: playback restarts (new file or live session)
 output reg resync=0,               // one-cycle pulse: the demux must resynchronise (mount, forced switch)
 output reg live=0,                 // the mounted image is a live ring
 output reg [31:0] written=0,       // bytes of the file placed in the ring
 output reg [31:0] loops=0,
 output reg [39:0] start_byte=0,    // where this mount joined the file
 // DDR3 write port (single 64-bit beats)
 output reg mem_req=0,output reg [28:0] mem_addr=0,output reg [63:0] mem_wdata=0,output reg [7:0] mem_be=8'hff,
 input wire mem_accept
);
 localparam integer RING=1<<RING_BITS;
 localparam integer CHUNK_BLOCKS=16;            // 8 KiB per request
 localparam integer CHUNK=CHUNK_BLOCKS*512;
 // Block buffer: hps_io writes 16-bit words at sd_buff_addr during sd_ack.
 (* ramstyle="M10K" *) reg [15:0] buffer[0:CHUNK/2-1];
 reg [11:0] rd_word=0;reg [15:0] rd_q=0;
 always @(posedge clk)begin
  if(sd_ack && sd_buff_wr)buffer[sd_buff_addr[11:0]]<=sd_buff_dout;
  rd_q<=buffer[rd_word];
 end
 reg [63:0] size=0;          // file size in bytes
 reg [31:0] total_blocks=0;  // blocks holding file data (last one may be partial)
 reg [39:0] file_pos=0;      // byte offset in the file of the next request (files may exceed 4 GiB)
 reg [31:0] chunk_bytes=0;   // valid file bytes in the current request
 localparam IDLE=0,REQUEST=1,TRANSFER=2,COPY_READ=3,COPY_WAIT=4,COPY_WRITE=5,
            HEAD_REQ=6,HEAD_WAIT=7,HEAD_READ=8,HEAD_PARSE=9,JOIN_MUL=10,JOIN_MOD=11,JOIN_ALIGN=12,
            STAT_REQ=13,STAT_WAIT=14;
 reg [3:0] state=IDLE;
 // stream-info header and join arithmetic
 reg [7:0] head[0:23];reg [4:0] head_i=0;
 reg [16:0] anchor=0;reg [16:0] elapsed=0;reg behind=0;
 reg [47:0] num=0,den=0,rem=0;reg [6:0] bit_i=0;reg mod_stage=0;
 wire head_ok=head[0]==8'h47 && head[1][4:0]==5'h1f && head[2]==8'hfe &&
              head[4]=="P" && head[5]=="A" && head[6]=="C" && head[7]=="E" &&
              head[8]=="S" && head[9]=="T" && head[10]=="R" && head[11]=="M";
 wire [31:0] head_anchor={head[12],head[13],head[14],head[15]};
 wire head_live=head[0]==8'h47 && head[1][4:0]==5'h1f && head[2]==8'hfe &&
              head[4]=="P" && head[5]=="A" && head[6]=="C" && head[7]=="E" &&
              head[8]=="L" && head[9]=="I" && head[10]=="V" && head[11]=="E";
 wire [31:0] head_session={head[12],head[13],head[14],head[15]};
 wire [31:0] head_written={head[16],head[17],head[18],head[19]};
 wire [31:0] head_ring={head[20],head[21],head[22],head[23]};
 // ---- live mode
 reg polling=0;                       // this header read is a poll, not a mount
 reg [31:0] session=0,src_written=0,ring_mask=0,seq=0;
 reg [31:0] new_session=0,new_written=0;
 reg pending_switch=0;reg [22:0] switch_timer=0;
 reg [21:0] poll_timer=0;
 wire [31:0] src_ahead=src_written-file_pos[31:0];   // relay bytes not yet read (modular)
 wire src_chunk=!src_ahead[31] && src_ahead>=CHUNK;
 // status block (first 32 bytes of block 1), latched when the write is
 // requested; hps_io fetches 16-bit words, low byte first in the file
 reg [255:0] stat=0;
 wire [3:0] stat_w=sd_buff_addr[3:0];
 always @(posedge clk)
  sd_buff_din<=sd_buff_addr[12:4]==0 ? {stat[247-16*stat_w-:8],stat[255-16*stat_w-:8]} : 16'h0000;
 reg [1:0] lane=0;           // 16-bit word within the 64-bit DDR word
 reg [31:0] copy_word=0;     // 16-bit words of this chunk copied so far
 reg [31:0] copy_words=0;
 reg [31:0] wr_ptr=0;        // ring byte offset of the next 64-bit word (multiple of 8)
 wire [31:0] room=RING-(written-played);
 always @(posedge clk)begin
  restart<=0;resync<=0;
  if(poll_timer!=0)poll_timer<=poll_timer-1'b1;
  if(pending_switch && switch_timer!=0)switch_timer<=switch_timer-1'b1;
  if(reset)begin
   state<=IDLE;active<=0;sd_rd<=0;sd_wr<=0;mem_req<=0;written<=0;loops<=0;live<=0;pending_switch<=0;
  end else begin
   if(img_mounted)begin
    // New file (or unmount, size 0): start again from its first byte.
    size<=img_size;total_blocks<=32'((img_size[39:0]+40'd511)>>9);
    active<=img_size!=0;restart<=1;resync<=1;state<=IDLE;sd_rd<=0;sd_wr<=0;mem_req<=0;
    file_pos<=0;written<=0;wr_ptr<=0;loops<=0;start_byte<=0;live<=0;polling<=0;pending_switch<=0;
    if(img_size!=0)state<=HEAD_REQ;
   end else case(state)
    // ---- read block 0 for the stream-info packet
    HEAD_REQ:begin sd_lba<=0;sd_blk_cnt<=0;sd_rd<=1;state<=HEAD_WAIT;end
    HEAD_WAIT:if(sd_ack)sd_rd<=0;else if(!sd_rd)begin rd_word<=0;head_i<=0;state<=HEAD_READ;end
    HEAD_READ:begin   // two cycles per word: address, then data
     if(head_i[0])begin head[{head_i[4:1],1'b0}]<=rd_q[7:0];head[{head_i[4:1],1'b1}]<=rd_q[15:8];rd_word<=rd_word+1'b1;end
     head_i<=head_i+1'b1;
     if(head_i==5'd23)state<=HEAD_PARSE;
    end
    HEAD_PARSE:if(polling)begin
     // live poll: follow the relay; a new session switches streams
     if(head_live)begin
      if(head_session!=session)begin
       if(!pending_switch)switch_timer<=23'(SWITCH_WAIT);
       pending_switch<=1;new_session<=head_session;new_written<=head_written;
      end else src_written<=head_written;
     end
     state<=IDLE;
    end else begin
     if(head_live && head_ring>=32'd65536 && (head_ring&(head_ring-1))==0)begin
      live<=1;session<=head_session;src_written<=head_written;ring_mask<=head_ring-1;poll_timer<=0;
      state<=IDLE;
     end else if(head_ok && now_valid && head_anchor<32'd86400)begin
      behind<=now_seconds<head_anchor[16:0];
      elapsed<=now_seconds>=head_anchor[16:0] ? now_seconds-head_anchor[16:0] : head_anchor[16:0]-now_seconds;
      state<=JOIN_MUL;
     end else state<=IDLE;
    end
    JOIN_MUL:begin num<={31'd0,elapsed}*RATE;den<=size[47:0];mod_stage<=0;rem<=0;bit_i<=7'd47;state<=JOIN_MOD;end
    JOIN_MOD:begin
     // restoring remainder, one bit per clock: rem = num mod den
     if(({rem[46:0],num[bit_i]})>=den)rem<={rem[46:0],num[bit_i]}-den;
     else rem<={rem[46:0],num[bit_i]};
     if(bit_i==0)state<=JOIN_ALIGN;else bit_i<=bit_i-1'b1;
    end
    JOIN_ALIGN:begin
     if(!mod_stage)begin
      // now rem = |now - anchor| * RATE mod size; before the anchor the
      // offset counts back from the end of the period. Second pass: mod 24064.
      num<=(behind && rem!=0) ? size[47:0]-rem : rem;den<=48'd24064;rem<=0;bit_i<=7'd47;mod_stage<=1;
      start_byte<=(behind && rem!=0) ? size[39:0]-rem[39:0] : rem[39:0];state<=JOIN_MOD;
     end else begin
      file_pos<=start_byte-rem[39:0];start_byte<=start_byte-rem[39:0];state<=IDLE;
     end
    end
    // ---- live: status write (block 1), then a header poll (block 0)
    STAT_REQ:begin sd_lba<=1;sd_blk_cnt<=0;sd_wr<=1;state<=STAT_WAIT;end
    STAT_WAIT:if(sd_ack)sd_wr<=0;else if(!sd_wr)begin seq<=seq+1'b1;polling<=1;state<=HEAD_REQ;end
    IDLE:if(live)begin
     if(pending_switch && (boundary || switch_timer==0))begin
      // the outgoing stream stops between packets (or, stalled, with a resync)
      restart<=1;resync<=!boundary;pending_switch<=0;
      session<=new_session;src_written<=new_written;file_pos<=0;written<=0;wr_ptr<=0;loops<=loops+1'b1;
     end else if(poll_timer==0 || (!src_chunk && poll_timer<22'(POLL_MAX-POLL_MIN)))begin
      poll_timer<=22'(POLL_MAX);
      stat<={"PACESTAT",session,file_pos[31:0],video_pid,audio_pid,seq,played,underruns};
      state<=STAT_REQ;
     end else if(room>=CHUNK && src_chunk)begin
      sd_lba<=32'd2+((file_pos[31:0]&ring_mask)>>9);sd_blk_cnt<=6'(CHUNK_BLOCKS-1);
      chunk_bytes<=CHUNK;sd_rd<=1;state<=REQUEST;
     end
    end else if(active && room>=CHUNK)begin
     sd_lba<=32'(file_pos>>9);
     sd_blk_cnt<=(total_blocks-32'(file_pos>>9))>=CHUNK_BLOCKS ? 6'(CHUNK_BLOCKS-1) : 6'(total_blocks-32'(file_pos>>9)-1);
     chunk_bytes<=(size[39:0]-file_pos)>=CHUNK ? CHUNK : 32'(size[39:0]-file_pos);
     sd_rd<=1;state<=REQUEST;
    end
    REQUEST:if(sd_ack)begin sd_rd<=0;state<=TRANSFER;end
    TRANSFER:if(!sd_ack)begin
     // Whole 64-bit words: stream files hold an even number of 188-byte
     // packets, so every request is a multiple of 8 bytes and the loop joins
     // packet-aligned (the channel builder pads with a null packet).
     copy_words<=chunk_bytes>>1;copy_word<=0;lane<=0;rd_word<=0;state<=COPY_READ;
    end
    COPY_READ:state<=COPY_WAIT;           // buffer read latency
    COPY_WAIT:begin
     // hps_io delivers bytes little-endian within each 16-bit word, which is
     // the byte order the DDR word needs (byte n at bits 8n+7..8n).
     mem_wdata[lane*16+:16]<=rd_q;
     copy_word<=copy_word+1'b1;rd_word<=rd_word+1'b1;
     if(lane==2'd3)begin
      mem_req<=1;mem_addr<=BASE+{3'd0,wr_ptr[RING_BITS-1:3]};mem_be<=8'hff;state<=COPY_WRITE;
     end else begin lane<=lane+1'b1;state<=COPY_READ;end
    end
    COPY_WRITE:if(mem_accept)begin
     mem_req<=0;lane<=0;wr_ptr<=wr_ptr+32'd8;written<=written+32'd8;
     if(copy_word>=copy_words)begin
      // chunk done; the file loops at its end
      if(live)file_pos<=file_pos+{8'd0,chunk_bytes};
      else if(file_pos+{8'd0,chunk_bytes}>=size[39:0])begin file_pos<=0;loops<=loops+1'b1;end
      else file_pos<=file_pos+{8'd0,chunk_bytes};
      state<=IDLE;
     end else state<=COPY_READ;
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
