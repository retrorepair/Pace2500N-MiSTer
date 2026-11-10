`timescale 1ns/1ps
module tb_transport;
 reg clk=0,reset=1,hold=0;always #5 clk=~clk;
 `include "sim/transport_vectors/sizes.vh"
 reg [63:0] storage[0:(TS_BYTES+7)/8-1];
 reg [31:0] expected[0:DMA_BYTES-1];
 wire valid,ready,reader_valid;wire [7:0] data,reader_data;
 reg manual=0,manual_valid=0,stream_reset=0;reg [7:0] manual_data=0;
 assign valid=manual?manual_valid:reader_valid;assign data=manual?manual_data:reader_data;
 wire rq,ra,rv,dq,da,irq,config_ready;wire [28:0] rad,dad;wire [63:0] dwd;wire [7:0] dbe;
 wire [31:0] loops,packets,sections,dropped,crc_errors;
 reg [63:0] returned=0;reg response=0,pending=0;reg [3:0] latency=0;
 reg [31:0] cycle=0,writes=0;
 reg io_req=0,io_we=0;reg [31:0] ia=0,id=0;reg [1:0] iz=2;wire [31:0] ir;
 assign ra=rq && !pending && cycle%7>2;
 assign rv=response;
 assign da=dq && cycle%9>3;
 pace_ts_replay #(.BYTE_CLOCKS(2)) reader(.clk(clk),.reset(reset),.hold(hold || manual),.enabled(1'b1),
  .length(24'(TS_BYTES)),.valid(reader_valid),.ready(ready && !manual),.data(reader_data),.loops(loops),
  .mem_req(rq),.mem_addr(rad),.mem_accept(ra),.mem_rvalid(rv),.mem_rdata(returned));
 pace_section_demux dut(.clk(clk),.reset(reset),.hold(hold),.stream_reset(stream_reset),
  .ts_valid(valid),.ts_ready(ready),.ts_data(data),
  .io_req(io_req),.io_we(io_we),.io_addr(ia),.io_wdata(id),.io_size(iz),.io_rdata(ir),.irq(irq),.config_ready(config_ready),
  .mem_req(dq),.mem_addr(dad),.mem_wdata(dwd),.mem_be(dbe),.mem_accept(da),
  .packets(packets),.sections(sections),.dropped(dropped),.crc_errors(crc_errors));
 integer lane,check_index;
 always @(posedge clk)begin
  cycle<=cycle+1;response<=0;
  if(pending)begin
   if(latency==0)begin pending<=0;response<=1;end else latency<=latency-1'b1;
  end
  if(ra)begin
   if(rad<29'h06600000 || rad>=29'h06600000+(TS_BYTES+7)/8)$fatal(1,"bad replay address %h",rad);
   returned<=storage[rad-29'h06600000];pending<=1;latency<=cycle%5;
  end
  if(da)begin
   for(lane=0;lane<8;lane=lane+1)if(dbe[lane])begin
    if(writes>=DMA_BYTES)$fatal(1,"extra DMA write");
    if({(dad-29'h06000000)*29'd8+29'(lane),dwd[lane*8+:8]}!={5'd0,expected[writes]})
     $fatal(1,"DMA byte %d got %h:%h expected %h",writes,(dad-29'h06000000)*8+lane,dwd[lane*8+:8],expected[writes]);
    writes<=writes+1;
   end
  end
 end
 task write_reg(input[31:0] address,value,input[1:0] size);
 begin
  while(!config_ready)@(negedge clk);
  @(negedge clk);io_req=1;io_we=1;ia=address;id=value;iz=size;
  @(negedge clk);io_req=0;io_we=0;
 end endtask
 task first_packet;
 integer n;
 begin
  @(negedge clk);stream_reset=1;
  @(negedge clk);stream_reset=0;
  for(n=0;n<188;n=n+1)begin
   manual_valid=1;manual_data=storage[n/8][(n%8)*8+:8];
   do @(posedge clk);while(!ready);
   @(negedge clk);
  end
  manual_valid=0;
  while(dut.state!=0)@(negedge clk);
  repeat(4)@(negedge clk);
 end endtask
 initial begin
  $readmemh("sim/transport_vectors/ts64.hex",storage);
  $readmemh("sim/transport_vectors/expected.hex",expected);
  repeat(4)@(negedge clk);reset=0;
  while(packets<TS_BYTES/188 || dut.state!=0)begin
   @(negedge clk);
   hold=cycle%61<5;
   io_req=0;io_we=0;
   if(irq && !hold)begin io_req=1;io_we=1;ia=32'hb000a0b8;id=0;iz=2;end
  end
  manual=1;hold=0;io_req=0;io_we=0;
  if(writes!=NORMAL_DMA_BYTES || sections!=5 || crc_errors!=1)$fatal(1,"counts writes %d sections %d crc %d",writes,sections,crc_errors);
  write_reg(32'hb000a0b8,0,2);
  // Program producer ten bytes before ring end and a nearly-full limit.
  write_reg(32'hb000a128,32'h00044ff6,2);write_reg(32'hb000a124,32'hc058,2);
  write_reg(32'hb000a128,32'h00044ffb,2);write_reg(32'hb000a124,32'hc05a,2);
  first_packet();if(writes!=NORMAL_DMA_BYTES)$fatal(1,"full ring overwritten");
  // Free enough room across the wrap, but route a rejecting logical unit17
  // (pair8 high). Channel22 owns route word96, bit17 selects that unit.
  write_reg(32'hb000a128,32'h00044fff,2);write_reg(32'hb000a124,32'hc058,2);
  write_reg(32'hb000a128,32'h00042064,2);write_reg(32'hb000a124,32'hc05a,2);
  write_reg(32'hb000a148,32'h00020000,2);write_reg(32'hb000a144,32'hc096,2);
  write_reg(32'hb000a148,32'h42ff0000,2);write_reg(32'hb000a144,32'hc008,2);
  first_packet();if(writes!=NORMAL_DMA_BYTES)$fatal(1,"high-half match bypassed");
  write_reg(32'hb000a148,32'h73ff0000,2);write_reg(32'hb000a144,32'hc008,2);
  first_packet();if(writes!=WRAP_DMA_BYTES || sections!=6 || !irq)$fatal(1,"wrapped delivery failed");
  if(dut.pointers[22]!=32'h0004201d)$fatal(1,"wrapped producer pointer %h",dut.pointers[22]);
  // W0C upper byte does not clear channel 22 in the next byte.
  write_reg(32'hb000a0b8,0,0);if(!irq)$fatal(1,"wrong BE byte cleared IRQ");
  write_reg(32'hb000a0b9,0,0);if(irq)$fatal(1,"BE status clear failed");
  // Two independently configured PID channels request the same packet. Each
  // owns its own assembly, match routing, guest ring, pointer and status bit.
  write_reg(32'hb000a078,32'h00014014,2);
  write_reg(32'hb000a148,32'h00000400,2);write_reg(32'hb000a144,32'hc099,2);
  first_packet();
  if(writes!=DMA_BYTES || sections!=8 || dut.status[2]!=32'h02400000)$fatal(1,"shared PID channels failed %h",dut.status[2]);
  write_reg(32'hb000a0b8,0,2);
  // BE subword enables are W1S, statuses W0C; command busy must read zero.
  write_reg(32'hb000a0db,32'h00000001,0);
  ia=32'hb000a0d8;iz=2;#1;
  if(ir!=32'hffc00001)$fatal(1,"bad BE enables %h",ir);
  ia=32'hb000a124;#1;if(ir!=0)$fatal(1,"command busy echoed");
  $display("PASS transport: %d packets, %d exact DMA bytes, %d sections; CRC, duplicates, loss, full ring, wrap, high-half masks, BE status",packets,writes,sections);
  write_reg(32'hb000a000,1,2);
  while(!config_ready)@(negedge clk);
  for(check_index=0;check_index<256;check_index=check_index+1)
   if(dut.match_words[check_index]!=0)$fatal(1,"software block reset did not clear match RAM %d",check_index);
  if(dut.enables[2]!=0 || dut.pids[22]!=0)$fatal(1,"software reset left PID/enables active");
  reset=1;repeat(4)@(negedge clk);reset=0;
  while(!config_ready)@(negedge clk);
  if(dut.match_words[8'h50]!=32'h000073ff || dut.match_words[8'h69]!=32'h00000400)$fatal(1,"checkpoint seed reload failed");
  $display("PASS filter block RAM: sequential software clear and checkpoint seed restore");
  $finish;
 end
 initial begin #20000000;$fatal(1,"timeout");end
endmodule
