`timescale 1ns/1ps
// Source handover while a real DDR read is in flight. Run with +CONTROLLED
// +STILL and the firmware-derived padded still (same args as capture test).
module tb_mpeg_restart;
 tb_mpeg_video b();
 integer sequence_before,cycles_waited,reset_cycles=256;
 initial begin
  if($value$plusargs("RESET_CYCLES=%d",reset_cycles))begin end
  wait(!b.reset);
  @(negedge b.clk_sys);b.enable_in=1;b.stream_enable=1;
  wait(b.position>=7000);
  @(negedge b.clk_sys);b.stream_enable=0;
  // A burst tail does not exercise a response arriving in the NEW decoder
  // epoch. FIRST_BEAT waits for a command still in its initial latency; use
  // MEM_LAT longer than both reset walks to force that overlap.
  if($test$plusargs("FIRST_BEAT"))wait(b.rd_left!=0 && b.rd_wait>0);
  else wait(b.rd_left!=0);
  @(negedge b.clk_sys);b.enable_in=0;b.flush_in=1;
  $display("RESET with %0d DDR beats pending, latency remaining %0d, shim state %0d",b.rd_left,b.rd_wait,b.dut.memory.state);
  repeat(reset_cycles)@(negedge b.clk_sys);
  b.flush_in=0;
  repeat(reset_cycles)@(negedge b.clk_sys);
  sequence_before=b.n_seq;
  // Only the OLD accepted request needs the long latency. Keep normal memory
  // performance for the fresh stream; rd_wait for that old burst is untouched.
  if($test$plusargs("FIRST_BEAT"))b.memory_latency=6;
  b.position=0;b.enable_in=1;b.stream_enable=1;
  cycles_waited=0;
  while(!b.capture_valid && cycles_waited<7500000)begin
   @(negedge b.clk_sys);cycles_waited=cycles_waited+1;
  end
  if(!b.capture_valid || b.n_seq==sequence_before)
   $fatal(1,"Restart failed: input%0d busy%b decoder_rst%b init%0d shim_state%0d seq%0d/%0d",
     b.position,b.busy,b.dut.sync_rst,b.dut.decoder.init_cnt,b.dut.memory.state,b.n_seq,sequence_before);
  $display("PASS: decoder reset during a DDR read -> fresh sequence header and completed picture");$finish;
 end
 initial begin #250000000;$fatal(1,"Restart test timeout");end
endmodule
