`timescale 1ns/1ps
module tb_timer;
 reg clk=0,reset=1;always #5 clk=~clk;
 integer phase,k;reg [31:0] before_count;
 pace_firmware_cpu DUT(.clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd0),
  .mem_accept(1'b0),.mem_rvalid(1'b0),.mem_rdata(64'd0));
 task init_case;
 begin
  @(negedge clk);reset=1;repeat(3)@(negedge clk);reset=0;
  DUT.boot_memory.words[0]=0;DUT.boot_memory.words[1]=0;
  DUT.cp0[9]=100;DUT.cp0[11]=101;DUT.timer_armed=1;
 end endtask
 initial begin
  // Eligibility: IE, EXL, ERL, IM7 and BEV.
  for(phase=0;phase<7;phase=phase+1)begin
   init_case();
   case(phase)
    0:DUT.cp0[12]=32'h8001;
    1:DUT.cp0[12]=32'h408001;
    2:DUT.cp0[12]=32'h8000;
    3:DUT.cp0[12]=32'h8003;
    4:DUT.cp0[12]=32'h8005;
    5:DUT.cp0[12]=32'h1;
    6:begin DUT.cp0[12]=32'h8001;DUT.mips16=1;end
   endcase
   @(negedge clk);
   if(phase==0 || phase==1 || phase==6)begin
    if(DUT.interrupt_count!==1 || DUT.pc!==(phase==1?32'hbfc00380:32'h80000180) ||
       DUT.cp0[14]!==(phase==6?32'hbfc00001:32'hbfc00000) || DUT.mips16!==0 ||
       DUT.cp0[12][1]!==1 || DUT.cp0[13]!==32'h8000)$fatal(1,"IRQ eligibility phase %d",phase);
   end else if(DUT.interrupt_count!==0 || DUT.cp0[13]!==32'h8000)$fatal(1,"IRQ mask phase %d",phase);
  end
  // Count advances while DDR is stalled, independent of retired instructions.
  phase=7;init_case();DUT.pc=32'hbfc20000;DUT.cp0[12]=0;
  before_count=DUT.cp0[9];repeat(25)@(negedge clk);
  if(DUT.cp0[9]!==before_count+25 || DUT.retired!==0 || DUT.state!==4)$fatal(1,"free-running Count");
  // Compare acknowledges IP7 and arms; Cause writes only affect software IP.
  phase=8;init_case();DUT.timer_armed=0;DUT.cp0[13]=32'h8000;DUT.gpr[8]=1000;
  DUT.boot_memory.words[0]=32'h40885800; // MTC0 t0,Compare
  wait(DUT.retired==1);@(negedge clk);
  if(DUT.cp0[11]!==1000 || DUT.cp0[13][15]!==0 || !DUT.timer_armed)$fatal(1,"Compare acknowledgement");
  phase=9;init_case();DUT.timer_armed=0;DUT.cp0[13]=32'h8000;DUT.gpr[8]=32'hffffffff;
  DUT.boot_memory.words[0]=32'h40886800; // MTC0 t0,Cause
  wait(DUT.retired==1);@(negedge clk);
  if(DUT.cp0[13]!==32'h8300)$fatal(1,"Cause writable mask %h",DUT.cp0[13]);
  // Interrupt immediately before either taken or untaken branch delay slot.
  for(phase=10;phase<13;phase=phase+1)begin
   init_case();DUT.timer_armed=0;
   if(phase==12)begin
    DUT.mips16=1;DUT.boot_memory.words[0]=32'he8204800;DUT.gpr[31]=32'hbfc00101;
   end else begin
    DUT.boot_memory.words[0]=phase==10?32'h10000003:32'h14000003;
   end
   wait(DUT.retired==1);@(negedge clk);
   if(!DUT.delay_slot)$fatal(1,"delay-slot tracking phase %d",phase);
   DUT.cp0[12]=32'h8001;DUT.cp0[13]=32'h8000;
   @(negedge clk);
   if(DUT.cp0[14]!==(phase==12?32'hbfc00001:32'hbfc00000) || DUT.cp0[13]!==32'h80008000 || DUT.branch_pending || DUT.delay_slot)
    $fatal(1,"delay IRQ EPC/BD phase %d EPC %h Cause %h",phase,DUT.cp0[14],DUT.cp0[13]);
  end
  $display("PASS: Count/Compare, masks, software Cause bits, BEV, MIPS16 EPC, taken/untaken delay BD");$finish;
 end
 initial begin #100000;$fatal(1,"timer test timeout");end
endmodule

