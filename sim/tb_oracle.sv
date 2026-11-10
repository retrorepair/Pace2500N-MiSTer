`timescale 1ns/1ps
module tb_oracle;
 reg clk=0,reset=1;always #5 clk=~clk;
 wire req,we;wire [28:0] addr;wire [63:0] wdata;wire [7:0] be;
 reg rvalid=0;reg [63:0] rdata=0;
 reg [63:0] memory[0:8191];
 integer cycles=0,pending=0,read_index=0,lane,n,k,case_id;
 wire accept=req && cycles%4==2;
 pace_firmware_cpu DUT(.clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd0),
  .mem_req(req),.mem_we(we),.mem_addr(addr),.mem_wdata(wdata),.mem_be(be),
  .mem_accept(accept),.mem_rvalid(rvalid),.mem_rdata(rdata));
 always @(posedge clk)begin
  cycles<=cycles+1;rvalid<=0;
  if(reset)pending<=0;
  else begin
   if(pending>0)begin
    pending<=pending-1;
    if(pending==1)begin rvalid<=1;rdata<=memory[read_index];end
   end
   if(req && accept)begin
    if(addr<29'h06000000 || addr>=29'h06002000)$fatal(1,"unexpected DDR address %h",addr);
    if(we)begin
     for(lane=0;lane<8;lane=lane+1)if(be[lane])memory[addr-29'h06000000][lane*8+:8]<=wdata[lane*8+:8];
    end else begin
     if(pending!=0)$fatal(1,"overlapping DDR requests");
     pending<=3;read_index<=addr-29'h06000000;
    end
   end
  end
 end
 // Registers live in block RAM plus T/SP/RA copies; preset every view.
 task set_gpr(input integer index,input [31:0] value);
 begin
  DUT.gpr[index]=value;DUT.gpr_ram_a[index]=value;DUT.gpr_ram_b[index]=value;
  if(index==24)DUT.reg_t=value;if(index==29)DUT.reg_sp=value;if(index==31)DUT.reg_ra=value;
 end endtask
 task init_case(input integer id,input [31:0] pc,input mode16);
 begin
  @(negedge clk);reset=1;repeat(2)@(negedge clk);
  for(n=0;n<8192;n=n+1)memory[n]=0;
  for(n=31744;n<32000;n=n+1)DUT.boot_memory.words[n]=0;
  for(n=0;n<32;n=n+1)set_gpr(n,0);
  reset=0;case_id=id;DUT.pc=pc;DUT.mips16=mode16;
 end endtask
 task put_byte(input [31:0] address,input [7:0] value);
 begin
  if(address>=32'hbfc00000)DUT.boot_memory.words[(address&32'h1ffff)>>2][(3-address[1:0])*8+:8]=value;
  else memory[address[15:3]][address[2:0]*8+:8]=value;
 end endtask
 task execute_case(input integer count);
 begin
  k=0;
  while(DUT.retired<count && DUT.halt_code==0 && k<500)begin @(negedge clk);k=k+1;end
  if(DUT.halt_code!=0 || DUT.retired!=count)$fatal(1,"case %0d timeout/halt=%h PC=%h IR=%h RET=%d",case_id,DUT.halt_code,DUT.pc,DUT.instruction,DUT.retired);
 end endtask
 task check_reg(input integer index,input [31:0] value);
  if(DUT.gpr[index]!==value)$fatal(1,"case %0d GPR%0d got %h expected %h",case_id,index,DUT.gpr[index],value);
 endtask
 task check_byte(input [31:0] address,input [7:0] value);
  if(memory[address[15:3]][address[2:0]*8+:8]!==value)$fatal(1,"case %0d memory %h",case_id,address);
 endtask
 initial begin
  `include "oracle_cases.svh"
  $display("PASS: 260 independent Ghidra oracle cases in RTL with DDR stalls");$finish;
 end
endmodule
