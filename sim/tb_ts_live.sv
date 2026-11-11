`timescale 1ns/1ps
// pace_ts_stream live mode + pace_ts_replay against a model of hps_io's block
// interface (reads AND the core's status-block writes) on a live ring file,
// filled by a model of tools/mister/pace_live_relay.py. Checks:
//  - every byte played equals the relay's session-1 byte at that position;
//  - the relay never overwrites unread data (it follows the status block);
//  - the status block carries "PACESTAT", the session and the A/V PIDs;
//  - a new session switches playback at a TS packet boundary of session 1,
//    and session 2 then plays from its byte 0, byte-exact.
module tb_ts_live;
 reg clk=0;always #10 clk=~clk;
 reg reset=1;
 localparam integer RING=65536;              // relay ring in the file (minimum)
 localparam integer RING_BITS=16;            // core's DDR ring
 localparam integer FILE_BYTES=1024+RING;
 localparam integer CHUNK=8192;
 reg [7:0] file[0:FILE_BYTES-1];
 function automatic [7:0] pattern(input integer s,input integer n);
  pattern=(n*7+(n>>8)*13+s*91+(n>>16)*5)&8'hff;
 endfunction
 integer i;
 // header fields (big-endian) at bytes 12..23
 task automatic put32(input integer a,input [31:0] v);
  file[a]=v[31:24];file[a+1]=v[23:16];file[a+2]=v[15:8];file[a+3]=v[7:0];
 endtask
 function automatic [31:0] get32(input integer a);
  get32={file[a],file[a+1],file[a+2],file[a+3]};
 endfunction
 initial begin
  for(i=0;i<FILE_BYTES;i=i+1)file[i]=8'h00;
  file[0]=8'h47;file[1]=8'h1f;file[2]=8'hfe;file[3]=8'h10;
  file[4]="P";file[5]="A";file[6]="C";file[7]="E";file[8]="L";file[9]="I";file[10]="V";file[11]="E";
  put32(12,32'd1);put32(16,32'd0);put32(20,RING);
 end
 // ---- hps_io block interface model (reads and writes)
 reg img_mounted=0;reg [63:0] img_size=0;
 wire [31:0] sd_lba;wire [5:0] sd_blk_cnt;wire sd_rd,sd_wr;wire [15:0] sd_buff_din;
 reg sd_ack=0,sd_buff_wr=0;reg [12:0] sd_buff_addr=0;reg [15:0] sd_buff_dout=0;
 integer words,w,base,gap,status_writes=0;
 initial forever begin
  @(posedge clk);
  if(sd_rd)begin
   repeat(50+($random&255))@(posedge clk);
   sd_ack<=1;base=sd_lba*512;words=(sd_blk_cnt+1)*256;
   for(w=0;w<words;w=w+1)begin
    @(posedge clk);
    sd_buff_addr<=w;
    sd_buff_dout<={file[base+2*w+1],file[base+2*w]};
    sd_buff_wr<=1;@(posedge clk);sd_buff_wr<=0;
    gap=$random&3;repeat(gap)@(posedge clk);
   end
   @(posedge clk);sd_ack<=0;
  end else if(sd_wr)begin
   repeat(50+($random&255))@(posedge clk);
   sd_ack<=1;base=sd_lba*512;words=(sd_blk_cnt+1)*256;
   for(w=0;w<words;w=w+1)begin
    @(posedge clk);sd_buff_addr<=w;
    repeat(3)@(posedge clk);            // SPI-paced: address stable for several clocks
    file[base+2*w]=sd_buff_din[7:0];file[base+2*w+1]=sd_buff_din[15:8];
   end
   @(posedge clk);sd_ack<=0;status_writes=status_writes+1;
  end
 end
 // ---- relay model: fills whole chunks while the core's read position allows
 integer session=1,relay_written=0,n,overwrites=0;
 reg [31:0] core_read;
 initial begin
  wait(!reset);
  forever begin
   repeat(200+($random&511))@(posedge clk);
   core_read=get32(512+12);
   if(get32(512+8)!=session)core_read=0;    // core has not picked this session up yet
   if(relay_written-core_read<=RING-CHUNK)begin
    for(n=0;n<CHUNK;n=n+1)file[1024+((relay_written+n)%RING)]=pattern(session,relay_written+n);
    relay_written=relay_written+CHUNK;
    put32(16,relay_written);
   end
  end
 end
 // ---- DDR3 model
 reg [63:0] mem[0:(1<<(RING_BITS-3))-1];
 wire [31:0] written,played,loops,underruns,rloops;
 wire sq;wire [28:0] sad;wire [63:0] swd;wire [7:0] sbe;
 wire tq;wire [28:0] tad;
 reg sa=0,ta=0,tv=0;reg [63:0] rdata=0;reg pending=0;reg [28:0] paddr=0;reg [3:0] lat=0;
 always @(posedge clk)begin
  sa<=0;ta<=0;tv<=0;
  if(pending)begin
   if(lat!=0)lat<=lat-1;else begin rdata<=mem[paddr-29'h06600000];tv<=1;pending<=0;end
  end else if(tq && !ta && ($random&1))begin ta<=1;pending<=1;paddr<=tad;lat<=$random&7;end
  else if(sq && !sa && ($random&1))begin sa<=1;mem[sad-29'h06600000]<=swd;end
 end
 wire restart,resync,streaming,live;
 wire [39:0] start_byte;
 reg [7:0] phase=0;
 wire valid;wire [7:0] data;
 always @(posedge clk)if(reset || restart)phase<=0;else if(valid)phase<=phase==187?0:phase+1;
 pace_ts_stream #(.RING_BITS(RING_BITS),.POLL_MAX(20000),.POLL_MIN(2000),.SWITCH_WAIT(100000)) dut(
  .clk(clk),.reset(reset),.now_seconds(17'd0),.now_valid(1'b1),.start_byte(start_byte),
  .img_mounted(img_mounted),.img_size(img_size),
  .sd_lba(sd_lba),.sd_blk_cnt(sd_blk_cnt),.sd_rd(sd_rd),.sd_wr(sd_wr),.sd_ack(sd_ack),.sd_buff_addr(sd_buff_addr),
  .sd_buff_dout(sd_buff_dout),.sd_buff_wr(sd_buff_wr),.sd_buff_din(sd_buff_din),
  .video_pid(16'h4200),.audio_pid(16'h4102),.underruns(underruns),.boundary(phase==0),
  .played(played),.active(streaming),.restart(restart),.resync(resync),.live(live),.written(written),.loops(loops),
  .mem_req(sq),.mem_addr(sad),.mem_wdata(swd),.mem_be(sbe),.mem_accept(sa && sq));
 pace_ts_replay #(.FAST_BYTE_CLOCKS(4)) player(.clk(clk),.reset(reset || restart),.hold(1'b0),.enabled(streaming),
  .length(27'(1<<RING_BITS)),.fast(1'b1),.stream(1'b1),.available(written),.played(played),.underruns(underruns),
  .valid(valid),.ready(1'b1),.data(data),.loops(rloops),.mem_req(tq),.mem_addr(tad),.mem_accept(ta && tq),.mem_rvalid(tv),.mem_rdata(rdata));
`ifdef DEBUG
 reg [3:0] last_state=15;
 always @(posedge clk)if(dut.state!=last_state && $time<20000000)begin
  last_state<=dut.state;
  $display("%t st=%0d live=%0d srcw=%0d fp=%0d room=%0d act=%0d hl=%0d ring=%h rd=%0d wr=%0d ack=%0d",$time,dut.state,dut.live,
   dut.src_written,dut.file_pos,dut.room,dut.active,dut.head_live,dut.head_ring,sd_rd,sd_wr,sd_ack);
 end
`endif
 // ---- checker
 integer cur=1,pos=0,errors=0,switched_at=-1,total=0,resyncs=0;
 always @(posedge clk)if(resync && live)resyncs=resyncs+1;
 always @(posedge clk)if(valid)begin
  if(data!==pattern(cur,pos))begin
   if(cur==1 && session==2 && pos%188==0 && data===pattern(2,0))begin cur=2;switched_at=pos;pos=0;end
   else begin errors=errors+1;if(errors<10)$display("session %0d byte %0d: got %h want %h",cur,pos,data,pattern(cur,pos));end
  end
  pos=pos+1;total=total+1;
 end
 reg stat_ok=0;
 initial begin
  repeat(10)@(posedge clk);reset=0;
  repeat(10)@(posedge clk);img_size<=FILE_BYTES;img_mounted<=1;@(posedge clk);img_mounted<=0;
  // play session 1 through several ring wraps, then switch mid-packet
  wait(total==5*RING+1001);
  stat_ok=file[512]=="P" && file[519]=="T" && get32(512+8)==1 && {file[528],file[529]}==16'h4200 && {file[530],file[531]}==16'h4102;
  session=2;relay_written=0;put32(16,0);put32(12,2);
  wait(cur==2 && pos==3*RING);
  $display("%s: session 1 played to byte %0d (packet-aligned: %0d), session 2 byte-exact for %0d bytes, errors %0d, status blocks %0d (fields %s), forced resyncs %0d, underrun cycles %0d",
   errors==0 && stat_ok && switched_at%188==0 && resyncs==0 ? "PASS":"FAIL",
   switched_at,switched_at%188==0,pos,errors,status_writes,stat_ok?"ok":"BAD",resyncs,underruns);
  $finish;
 end
 initial begin #2000000000;$display("TIMEOUT total=%0d cur=%0d pos=%0d written=%0d",total,cur,pos,written);$finish;end
endmodule
