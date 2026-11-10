`timescale 1ns/1ps
module tb_fetch;
 reg clk=0,reset=1;always #5 clk=~clk;
 wire req,we;wire [28:0] addr;wire [63:0] wdata;wire [7:0] be;
 reg rvalid=0;reg [63:0] rdata=0,latched;
 integer cycles=0,pending=0,n,k,phase;
 reg [7:0] flash[0:255],ram[0:511];
 wire accept=req && cycles%4==2;
 pace_firmware_cpu DUT(.clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd0),
  .mem_req(req),.mem_we(we),.mem_addr(addr),.mem_wdata(wdata),.mem_be(be),
  .mem_accept(accept),.mem_rvalid(rvalid),.mem_rdata(rdata));
 always @(posedge clk)begin
  cycles<=cycles+1;rvalid<=0;
  if(reset)pending<=0;
  else begin
   if(pending>0)begin pending<=pending-1;if(pending==1)begin rdata<=latched;rvalid<=1;end end
   if(req && accept)begin
    if(we || be!==8'hff)$fatal(1,"bad fetch request");
    if(addr>=29'h06404000 && addr<29'h06404020)
     for(n=0;n<8;n=n+1)latched[n*8+:8]<=flash[(addr-29'h06404000)*8+n];
    else if(addr>=29'h06000000 && addr<29'h06000040)
     for(n=0;n<8;n=n+1)latched[n*8+:8]<=ram[(addr-29'h06000000)*8+n];
    else $fatal(1,"unexpected address %h",addr);
    pending<=3;
   end
  end
 end
 task init_case;
 begin
  @(negedge clk);reset=1;repeat(3)@(negedge clk);
  for(k=0;k<256;k=k+1)flash[k]=0;
  for(k=0;k<512;k=k+1)ram[k]=0;
  reset=0;
 end endtask
 task execute(input integer count);
 begin
  k=0;while(DUT.retired<count && DUT.halt_code==0 && k<500)begin @(negedge clk);k=k+1;end
  if(DUT.retired!=count || DUT.halt_code!=0)$fatal(1,"phase %d halt %h PC %h",phase,DUT.halt_code,DUT.pc);
 end endtask
 initial begin
  for(phase=0;phase<2;phase=phase+1)begin
   init_case();DUT.pc=phase?32'h9fc1fffe:32'hbfc1fffe;DUT.mips16=1;
   DUT.boot_memory.words[32767]=32'h0000f7ff;flash[0]=8'h6a;flash[1]=8'h1f;
   execute(1);
   if(DUT.gpr[2]!==32'hffff || DUT.pc!==(phase?32'h9fc20002:32'hbfc20002))$fatal(1,"EXTEND boundary");
  end
  phase=2;init_case();DUT.pc=32'hbfc1fffe;DUT.mips16=1;
  DUT.boot_memory.words[32767]=32'h00001a1f;
  flash[0]=0;flash[1]=8'h60;flash[2]=8'h6a;flash[3]=8'h55;
  execute(2);
  if(DUT.gpr[2]!==32'h55 || DUT.gpr[31]!==32'hbfc20005 || DUT.pc!==32'hbfc00180)$fatal(1,"JAL boundary");
  phase=3;init_case();DUT.pc=32'h80000002;DUT.mips16=1;DUT.gpr[6]=32'h1234;
  ram[2]=8'hf4;ram[3]=0;ram[4]=8'h36;ram[5]=8'hc0;execute(1);
  if(DUT.gpr[6]!==32'h12340000 || DUT.pc!==32'h80000006)$fatal(1,"RAM extended fetch");
  for(phase=4;phase<8;phase=phase+1)begin
   init_case();DUT.boot_memory.words[0]=32'h42000018;
   DUT.cp0[12]=phase[1]?32'h6:32'h2;DUT.cp0[14]=32'h80000000|phase[0];
   DUT.cp0[30]=32'h80000010|phase[0];
   execute(1);
   if(DUT.pc!==(phase[1]?32'h80000010:32'h80000000) || DUT.mips16!==phase[0] ||
      DUT.cp0[12]!== (phase[1]?32'h2:32'h0))$fatal(1,"ERET state");
   // First instruction after ERET is really fetched from RAM.
   if(phase[0])begin ram[phase[1]?16:0]=8'h6a;ram[phase[1]?17:1]=8'h55;end
   else begin ram[phase[1]?16:0]=8'h24;ram[phase[1]?17:1]=8'h02;ram[phase[1]?18:2]=0;ram[phase[1]?19:3]=8'h55;end
   execute(2);if(DUT.gpr[2]!==32'h55)$fatal(1,"ERET RAM fetch");
  end
  phase=8;init_case();DUT.pc=32'hbfc00100;DUT.mips16=1;DUT.gpr[31]=32'hbfc00201;
  DUT.boot_memory.words[64]=32'he820f000;
  k=0;while(DUT.halt_code==0 && k<100)begin @(negedge clk);k=k+1;end
  if(DUT.halt_code!==8'h35 || DUT.retired!==1)$fatal(1,"EXTEND delay-slot diagnostic");
  $display("PASS: ROM/DDR boundary JAL+EXTEND, cached alias, RAM fetch, ERET and reserved delay");$finish;
 end
endmodule
