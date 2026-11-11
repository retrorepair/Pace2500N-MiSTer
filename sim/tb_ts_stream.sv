`timescale 1ns/1ps
// pace_ts_stream + pace_ts_replay in ring mode against a model of MiSTer's
// block interface (hps_io sd_*) and DDR3. Every byte the player emits must
// equal the file byte at that position, across several loops of the file.
module tb_ts_stream;
 reg clk=0;always #10 clk=~clk;
 reg reset=1;
 localparam integer FILE_BYTES=188*2*700;   // 263,200 bytes: not a multiple of 8 KiB or 512
 localparam integer RING_BITS=16;           // small ring so it wraps many times
 reg [7:0] file[0:FILE_BYTES-1];
 integer i;
 localparam [31:0] ANCHOR=32'd64800;        // 18:00:00 UTC
 // NOW before the anchor: the day-relative signed modulo the EPG uses,
 // ((NOW - ANCHOR) * RATE) mod FILE_BYTES with a non-negative result.
 localparam integer NOW=3600;              // 01:00 UTC
 reg [16:0] now_seconds=17'(NOW);
 localparam longint DIFF=(longint'(ANCHOR)-NOW)*781250;
 localparam longint BACK=DIFF%FILE_BYTES;
 localparam longint OFFSET=BACK==0 ? 0 : FILE_BYTES-BACK;
 localparam integer START=int'(OFFSET-(OFFSET%24064));
 initial begin
  for(i=0;i<FILE_BYTES;i=i+1)file[i]=(i*7+(i>>8)*13+3)&8'hff;
  // Pace stream-info packet at byte 0
  file[0]=8'h47;file[1]=8'h1f;file[2]=8'hfe;file[3]=8'h10;
  file[4]="P";file[5]="A";file[6]="C";file[7]="E";file[8]="S";file[9]="T";file[10]="R";file[11]="M";
  file[12]=ANCHOR[31:24];file[13]=ANCHOR[23:16];file[14]=ANCHOR[15:8];file[15]=ANCHOR[7:0];
 end
 // ---- hps_io block interface model
 reg img_mounted=0;reg [63:0] img_size=0;
 wire [31:0] sd_lba;wire [5:0] sd_blk_cnt;wire sd_rd;
 reg sd_ack=0,sd_buff_wr=0;reg [12:0] sd_buff_addr=0;reg [15:0] sd_buff_dout=0;
 integer words,w,base,gap;
 initial forever begin
  @(posedge clk);
  if(sd_rd)begin
   repeat(50+($random&255))@(posedge clk);       // Main's latency
   sd_ack<=1;base=sd_lba*512;words=(sd_blk_cnt+1)*256;
   for(w=0;w<words;w=w+1)begin
    @(posedge clk);
    sd_buff_addr<=w;
    sd_buff_dout<={ (base+2*w+1<FILE_BYTES)?file[base+2*w+1]:8'hee, (base+2*w<FILE_BYTES)?file[base+2*w]:8'hee };
    sd_buff_wr<=1;@(posedge clk);sd_buff_wr<=0;
    gap=$random&3;repeat(gap)@(posedge clk);
   end
   @(posedge clk);sd_ack<=0;
  end
 end
 // ---- DDR3 model with random accept delay and read latency
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
 wire stream_restart,streaming;
 wire [39:0] start_byte;
 pace_ts_stream #(.RING_BITS(RING_BITS)) dut(.clk(clk),.reset(reset),.now_seconds(now_seconds),.now_valid(1'b1),.start_byte(start_byte),.img_mounted(img_mounted),.img_size(img_size),
  .sd_wr(),.sd_buff_din(),.video_pid(16'h1fff),.audio_pid(16'h1fff),.underruns(underruns),.boundary(1'b1),.resync(),.live(),
  .sd_lba(sd_lba),.sd_blk_cnt(sd_blk_cnt),.sd_rd(sd_rd),.sd_ack(sd_ack),.sd_buff_addr(sd_buff_addr),.sd_buff_dout(sd_buff_dout),
  .sd_buff_wr(sd_buff_wr),.played(played),.active(streaming),.restart(stream_restart),.written(written),.loops(loops),
  .mem_req(sq),.mem_addr(sad),.mem_wdata(swd),.mem_be(sbe),.mem_accept(sa && sq));
 wire valid;wire [7:0] data;
 pace_ts_replay #(.FAST_BYTE_CLOCKS(4)) player(.clk(clk),.reset(reset || stream_restart),.hold(1'b0),.enabled(streaming),
  .length(27'(1<<RING_BITS)),.fast(1'b1),.stream(1'b1),.available(written),.played(played),.underruns(underruns),
  .valid(valid),.ready(1'b1),.data(data),.loops(rloops),.mem_req(tq),.mem_addr(tad),.mem_accept(ta && tq),.mem_rvalid(tv),.mem_rdata(rdata));
 integer n=0,errors=0;
 always @(posedge clk)if(valid)begin
  if(data!==file[(n+START)%FILE_BYTES])begin errors=errors+1;if(errors<10)$display("byte %0d: got %h want %h",n,data,file[(n+START)%FILE_BYTES]);end
  n=n+1;
 end
 initial begin
  repeat(10)@(posedge clk);reset=0;
  repeat(10)@(posedge clk);img_size<=FILE_BYTES;img_mounted<=1;@(posedge clk);img_mounted<=0;
  wait(n==3*FILE_BYTES+1000);
  $display("%s: joined at byte %0d (expected %0d), %0d bytes played, file loops %0d, ring wraps %0d, errors %0d, underrun cycles %0d",
   errors==0 && start_byte==START?"PASS":"FAIL",start_byte,START,n,loops,rloops,errors,underruns);
  $finish;
 end
 initial begin #2000000000;$display("TIMEOUT n=%0d written=%0d",n,written);$finish;end
endmodule
