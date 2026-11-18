// SPDX-License-Identifier: GPL-3.0-only
// The box's EEPROM kept in a file on the MiSTer's SD card: image slot 1 (MGL type "s",
// index 1, e.g. games/Pace2500N_GUIDE/EEPROM.bin, 64 KiB).
//
// A real 2500N keeps its I2C EEPROM through a power cut: the Personal Planner's bookings
// (/eeprom/book), favourites, PIN and the rest of its small file system live there. The core's
// EEPROM is block RAM, initialised from the checkpoint when the FPGA is configured, so without
// this a power cycle of the MiSTer lost everything the firmware had written to it.
//
// On mount the file is read twice, a 512-byte block at a time. The first pass only looks for
// a byte other than 0xFF: a file that is still blank (as install_relay.sh creates it) is not
// loaded, and every block is marked changed instead, so the first save writes the checkpoint's
// EEPROM into it. Otherwise the second pass copies the file into the EEPROM while the guest is
// held. After that, each block the firmware commits a write to is marked changed, and once the
// firmware has written nothing for about 0.2 s the changed blocks are written back one by one.
//
// Not reset by a core reset: the mount and the save state outlive a checkpoint reload.
module pace_eeprom_save #(parameter [23:0] QUIET=24'd16000000)(  // ~0.2 s of no EEPROM writes before saving
 input wire clk,reset,
 input wire img_mounted,input wire [63:0] img_size,
 output reg [31:0] sd_lba=0,output wire [5:0] sd_blk_cnt,output reg sd_rd=0,output reg sd_wr=0,
 input wire sd_ack,input wire [12:0] sd_buff_addr,input wire [15:0] sd_buff_dout,input wire sd_buff_wr,
 output wire [15:0] sd_buff_din,
 // the EEPROM's second port (rtl/pace_guide_peripherals.sv)
 output reg [15:0] ee_addr=0,output reg ee_we=0,output reg [7:0] ee_wdata=0,input wire [7:0] ee_q,
 // the firmware's own EEPROM writes (port A)
 input wire ee_commit_we,input wire [15:0] ee_commit_addr,
 output wire loading,
 output reg mounted=0,
 output reg [15:0] saved_blocks=0
);
 assign sd_blk_cnt=6'd0;

 // One 512-byte block, as 256 16-bit words (the low byte is the block's even byte, as
 // hps_io transfers them in WIDE mode).
 (* ramstyle="M10K" *) reg [15:0] block[0:255];
 reg [7:0] buf_raddr=0;reg [15:0] buf_q=0;
 reg buf_we=0;reg [7:0] buf_waddr=0;reg [15:0] buf_wdata=0;
 always @(posedge clk)begin
  if(buf_we)block[buf_waddr]<=buf_wdata;
  buf_q<=block[buf_raddr];
 end
 assign sd_buff_din=buf_q;

 localparam IDLE=0,SCAN_REQ=1,SCAN_WAIT=2,LOAD_REQ=3,LOAD_WAIT=4,LOAD_COPY=5,
            SAVE_COPY=6,SAVE_REQ=7,SAVE_WAIT=8;
 reg [3:0] state=IDLE;
 reg [7:0] blk=0;               // block number, 0-127
 reg acked=0;                   // sd_ack has risen for the current request
 reg nonblank=0;
 reg [127:0] dirty=0;
 reg [6:0] scan=0;
 reg [23:0] quiet=0;
 reg [9:0] i=0;                 // byte index within the block during a copy (0-512)
 reg [7:0] low=0;
 assign loading=(state>=SCAN_REQ && state<=LOAD_COPY) || ee_we;   // through the last byte's write

 wire sd_reading=(state==SCAN_WAIT || state==LOAD_WAIT) && sd_ack && sd_buff_wr;

 always @(posedge clk)begin
  ee_we<=0;
  buf_we<=0;
  if(reset)begin
   state<=IDLE;mounted<=0;sd_rd<=0;sd_wr<=0;dirty<=0;quiet<=0;
  end else begin
   if(ee_commit_we)quiet<=0;else if(quiet!=QUIET)quiet<=quiet+1'b1;
   // hps_io fills the block during a read; the first pass only checks for 0xFF
   if(sd_reading)begin
    if(state==LOAD_WAIT)begin buf_we<=1;buf_waddr<=sd_buff_addr[7:0];buf_wdata<=sd_buff_dout;end
    if(sd_buff_dout!=16'hffff)nonblank<=1;
   end
   if(img_mounted)begin
    mounted<=img_size>=64'd65536;sd_rd<=0;sd_wr<=0;dirty<=0;
    if(img_size>=64'd65536)begin blk<=0;nonblank<=0;state<=SCAN_REQ;end else state<=IDLE;
   end else case(state)
    IDLE:begin
     // clear the mark as the copy starts: a write committed during the copy marks it again
     if(mounted && dirty[scan] && quiet==QUIET)begin
      blk<={1'b0,scan};i<=0;dirty[scan]<=0;state<=SAVE_COPY;
     end else scan<=scan+1'b1;
    end
    SCAN_REQ:begin sd_lba<={24'd0,blk};sd_rd<=1;acked<=0;state<=SCAN_WAIT;end
    SCAN_WAIT:if(sd_ack)begin sd_rd<=0;acked<=1;end
     else if(acked)begin
      if(blk!=8'd127)begin blk<=blk+1'b1;state<=SCAN_REQ;end
      else if(nonblank)begin blk<=0;state<=LOAD_REQ;end
      else begin dirty<={128{1'b1}};state<=IDLE;end   // blank file: fill it from the EEPROM
     end
    LOAD_REQ:begin sd_lba<={24'd0,blk};sd_rd<=1;acked<=0;state<=LOAD_WAIT;end
    LOAD_WAIT:if(sd_ack)begin sd_rd<=0;acked<=1;end
     else if(acked)begin i<=0;buf_raddr<=0;state<=LOAD_COPY;end
    LOAD_COPY:begin
     // buf_q holds word i>>1 one clock after buf_raddr selects it: hold each word two clocks
     if(i!=0)begin
      ee_we<=1;ee_addr<={blk[6:0],i[8:0]-9'd1};
      ee_wdata<=(i[0] ? buf_q[7:0] : buf_q[15:8]);
     end
     if(i==10'd512)begin
      if(blk!=8'd127)begin blk<=blk+1'b1;state<=LOAD_REQ;end else state<=IDLE;
     end else begin i<=i+1'b1;buf_raddr<=(i+10'd1)>>1;end
    end
    SAVE_COPY:begin
     // ee_addr is registered and so is port B's output: byte k is on ee_q at i = k + 2
     if(i<10'd512)ee_addr<={blk[6:0],i[8:0]};
     if(i>=10'd2)begin
      if(!i[0])low<=ee_q;                                         // k = i - 2 even
      else begin buf_we<=1;buf_waddr<=8'((i-10'd2)>>1);buf_wdata<={ee_q,low};end
     end
     if(i==10'd513)begin buf_raddr<=0;state<=SAVE_REQ;end
     else i<=i+1'b1;
    end
    SAVE_REQ:begin sd_lba<={24'd0,blk};sd_wr<=1;acked<=0;state<=SAVE_WAIT;end
    SAVE_WAIT:begin
     buf_raddr<=sd_buff_addr[7:0];
     if(sd_ack)begin sd_wr<=0;acked<=1;end
     else if(acked)begin saved_blocks<=saved_blocks+1'b1;state<=IDLE;end
    end
    default:state<=IDLE;
   endcase
   // a write committed during a save marks its block again (after the clear above)
   if(ee_commit_we)dirty[ee_commit_addr[15:9]]<=1;
  end
 end
endmodule
