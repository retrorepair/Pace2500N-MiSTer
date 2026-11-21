`timescale 1ns/1ps
// Integration: original firmware still ES -> real MPEG decoder DDR -> DMA7.
// Run with +STILL +ES=... +BYTES=... +FIELDS=16 +OUT=/tmp/capture-field.
module tb_video_capture_path;
 tb_mpeg_video b();
 reg start=0,io_write=0;reg [31:0] io_addr=0,io_wdata=0;
 wire busy,done,req,we;wire [7:0] error,be;wire [28:0] addr;wire [63:0] wdata;
 reg rvalid=0;reg [63:0] rdata=0;
 integer plane=0,writes=0,finished=0,y_min=255,y_max=0;
 // Optional independent, unsigned planar YUV420 reference (e.g. FFmpeg's
 // decode of the original flash still). Allow one unit of IDCT rounding.
 reg [7:0] reference_yuv[0:622079];
 string reference_file;
 reg reference_enabled=0;
 integer reference_index,reference_error,reference_max_error=0;
 initial if($value$plusargs("YUV_REF=%s",reference_file))begin
  $readmemh(reference_file,reference_yuv);reference_enabled=1;
 end
 reg [1:0] held_frame=0;reg checking=0;
 always @* b.capture_hold=busy;
 always @(posedge b.clk_sys)if(done)b.keep_picture_in<=1;
 pace_video_capture_dma dut(.clk(b.clk_sys),.reset(b.reset),.hold(1'b0),.start(start),.stop(1'b0),
  .descriptor(32'h100),.io_write(io_write),.io_addr(io_addr),.io_wdata(io_wdata),
  .field_tick(b.field_evt),.frame_valid(b.capture_valid),.frame_id(b.capture_frame),
  .frame_mb_width(b.capture_mb_width),.frame_width(b.seq_h),.frame_height(b.seq_v),
  .busy(busy),.done(done),.error(error),.mem_req(req),.mem_write(we),.mem_addr(addr),
  .mem_wdata(wdata),.mem_be(be),.mem_accept(1'b1),.mem_rvalid(rvalid),.mem_rdata(rdata));
 function automatic [63:0] pair(input [31:0] low,high);
  integer lane;begin
   for(lane=0;lane<4;lane=lane+1)begin
    pair[lane*8+:8]=low[31-lane*8-:8];pair[(lane+4)*8+:8]=high[31-lane*8-:8];
   end
  end
 endfunction
 integer lane,row,column,source_word,expected_component,source_x,source_lane;
 reg [7:0] expected_byte;reg [63:0] source_data;
 always @(posedge b.clk_sys)begin
  rvalid<=0;
  if(req)begin
   if(we)begin
    if(addr!=29'h06040000+writes || be!=8'hff)$fatal(1,"Bad guest destination");
    if(b.capture_frame!=held_frame)$fatal(1,"Picture bank changed during copy");
    if(b.dut.decoder.resample.resample_addrgen.output_frame_sav!={1'b0,held_frame})
     $fatal(1,"Capture metadata disagrees with the decoder's displayed picture bank");
    row=(writes/90)*2+(plane&1);column=(writes%90)*8;
    for(lane=0;lane<8;lane=lane+1)begin
     source_x=plane<2 ? column+lane:(column+lane)/2;
     expected_component=plane<2 ? 0 : lane%2==0 ? 'h10000:'h14000;
     source_word=held_frame*'h18000+expected_component+row*(plane<2 ? 90:45)+source_x/8;
     source_data=b.mem[source_word];source_lane=source_x%8;
     expected_byte=source_data[63-source_lane*8-:8]^8'h80;
     if(wdata[lane*8+:8]!==expected_byte)$fatal(1,"Decoded pixel mismatch plane%0d word%0d lane%0d",plane,writes,lane);
     if(reference_enabled)begin
      reference_index=plane<2 ? row*720+source_x :
                          (lane%2==0 ? 414720:518400)+row*360+source_x;
      reference_error=int'(wdata[lane*8+:8])-int'(reference_yuv[reference_index]);
      if(reference_error<0)reference_error=-reference_error;
      if(reference_error>reference_max_error)reference_max_error=reference_error;
      if(reference_error>1)$fatal(1,"Independent YUV mismatch plane%0d row%0d x%0d got%0d expected%0d",
        plane,row,source_x,wdata[lane*8+:8],reference_yuv[reference_index]);
     end
     if(plane<2)begin
      if(expected_byte<y_min)y_min=expected_byte;
      if(expected_byte>y_max)y_max=expected_byte;
     end
    end
    writes=writes+1;
   end else begin
    rvalid<=1;
    case(addr)
     29'h06000021:rdata<=pair(0,0);
     29'h06000022:rdata<=pair(32'h00200000,32'h001c02d0);
     29'h06000023:rdata<=0;
     29'h06000024:rdata<=pair(32'h00200000+(plane<2 ? 207360:103680)-1,0);
     default:begin
      if(addr<29'h07000000 || addr>=29'h07060000)$fatal(1,"Bad decoded pixel address %h",addr);
      rdata<=b.mem[addr[21:0]];
     end
    endcase
   end
  end
  if(error!=0)$fatal(1,"DMA7 error %h",error);
  if(done)begin
   if(writes!=(plane<2 ? 25920:12960))$fatal(1,"Incomplete plane");
   finished=finished+1;
   $display("PASS decoded plane%0d frame%0d: %0d bytes",plane,held_frame,writes*8);
  end
 end
 task automatic store(input [31:0] a,d);
  @(negedge b.clk_sys);io_addr=a;io_wdata=d;io_write=1;
  @(negedge b.clk_sys);io_write=0;
 endtask
 initial begin
  wait(!b.reset);wait(b.capture_valid);
  for(plane=0;plane<4;plane=plane+1)begin
   writes=0;held_frame=b.capture_frame;
   @(negedge b.clk_sys);start=1;
   @(negedge b.clk_sys);start=0;
   store(32'hb00020dc,720);store(32'hb00020e0,576);
   store(32'hb00020d8,32'h8001|((plane&1)<<11)|(plane>=2 ? 'h400:0));
   wait(finished==plane+1);repeat(3)@(negedge b.clk_sys);
  end
  if(y_max-y_min<64)$fatal(1,"Captured flat/uninitialised image: Y range%0d..%0d",y_min,y_max);
  $display("Decoded image Y range %0d..%0d",y_min,y_max);
  if(reference_enabled)$display("PASS all622080 captured bytes match independent unsigned YUV420 reference within%0d",reference_max_error);
  @(negedge b.clk_sys);b.enable_in=0;b.stream_enable=0;b.flush_in=1;
  repeat(256)@(negedge b.clk_sys);b.flush_in=0;
  repeat(1000000)@(negedge b.clk_sys);
  if(!b.video_live || !b.capture_valid || b.capture_frame!=held_frame)
   $fatal(1,"Native DMA7 snapshot lost its displayed picture when ES input closed");
  $display("PASS native DMA7 snapshot remains displayed after its ES input closes");
  $display("PASS original firmware MPEG still -> DDR -> all four guest image planes");$finish;
 end
 initial begin #350000000;$fatal(1,"Decoder capture timeout");end
endmodule
