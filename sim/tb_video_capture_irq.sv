`timescale 1ns/1ps
// DMA7 controller contract used by original 80005900/80005D30 and DMA ISR.
module tb_video_capture_irq;
 reg clk=0;always #10 clk=~clk;
 reg reset=1,request=0,write=0,complete=0,gpu_done=0;
 reg [31:0] address=0,data=0;
 wire [31:0] result,descriptor;wire ready,irq,start,stop;
 wire [7:0] halt;
 pace_guide_peripherals #(.CAPTURE_DMA(1)) dut(.clk(clk),.reset(reset),.hold(1'b0),.retired(32'd0),
  .io_req(request),.io_we(write),.io_addr(address),.io_wdata(data),.io_size(2'd2),
  .io_rdata(result),.io_ready(ready),.io_irq(irq),.key_valid(1'b0),.key_pressed(1'b0),.key_code(8'd0),
  .gpu_done(gpu_done),.transport_irq(1'b0),.transport_lock(1'b0),.mpeg_irq(1'b0),.model_halt(halt),
  .ee_b_addr(16'd0),.ee_b_we(1'b0),.ee_b_wdata(8'd0),.cold(1'b1),.dma5_done(1'b0),
  .dma7_start(start),.dma7_stop(stop),.dma7_descriptor(descriptor),.dma7_done(complete));
 integer starts=0,stops=0;
 always @(posedge clk)begin if(start)starts=starts+1;if(stop)stops=stops+1;end
 task automatic store(input [31:0] a,d);
  @(negedge clk);address=a;data=d;write=1;request=1;
  @(negedge clk);request=0;write=0;
 endtask
 task automatic check(input [31:0] a,expected);
  @(negedge clk);address=a;request=1;write=0;#1;
  if(!ready || result!==expected)$fatal(1,"Register %h got%h expected%h",a,result,expected);
  @(negedge clk);request=0;
 endtask
 initial begin
  repeat(5)@(negedge clk);reset=0;
  store(32'hb0000040,2);
  store(32'hb00090b0,32'h00108b78);
  if(descriptor!=32'h00108b78)$fatal(1,"DMA7 descriptor not latched");
  store(32'hb0009010,32'h80);repeat(4)@(negedge clk);
  check(32'hb0009010,32'h80);check(32'hb0009120,0);
  if(starts!=1 || irq)$fatal(1,"Start acknowledged before copy");
  store(32'hb0009010,32'h1080);repeat(4)@(negedge clk);
  if(starts!=1)$fatal(1,"Other DMA start restarted capture");
  // Completion wins a simultaneous stale read-modify-write of START.
  @(negedge clk);complete=1;address=32'hb0009010;data=32'h1080;write=1;request=1;
  @(negedge clk);complete=0;request=0;write=0;
  repeat(3)@(negedge clk);
  check(32'hb0009010,32'h1000);check(32'hb0009120,32'h80);
  if(!irq || starts!=1)$fatal(1,"DMA7 interrupt missing or retriggered");
  store(32'hb0009130,32'h20);check(32'hb0009120,32'h80);
  store(32'hb0009130,32'h80);check(32'hb0009120,0);
  if(irq)$fatal(1,"DMA7 IRQ not acknowledged");
  // Another DMA can finish concurrently without losing either pending bit.
  store(32'hb0009010,32'h1080);
  @(negedge clk);complete=1;gpu_done=1;
  @(negedge clk);complete=0;gpu_done=0;
  check(32'hb0009120,32'h1080);check(32'hb0009010,0);
  store(32'hb0009130,32'h80);check(32'hb0009120,32'h1000);
  store(32'hb0009130,32'h1000);check(32'hb0009120,0);
  store(32'hb0009010,32'h80);store(32'hb0009010,0);
  repeat(4)@(negedge clk);check(32'hb0009120,0);
  if(stops!=1 || starts!=3 || irq || halt!=0)$fatal(1,"Stop/counters/IRQ: %0d/%0d/%b/%h",starts,stops,irq,halt);
  $display("PASS DMA7 descriptor, real-completion-only IRQ, stop, concurrent DMA and stale RMW");$finish;
 end
endmodule
