`timescale 1ns/1ps
// Execute the original guest ring-length helper at all header wrap positions.
module tb_ring_native;
 reg clk=0,reset=1,hold=1;always #5 clk=~clk;
 reg restore_wr=0;reg[6:0] restore_index=0;reg[31:0] restore_data=0;
 reg[31:0] words[0:68];reg[63:0] ram[0:2097151];
 wire req,we,accept;wire[28:0] address;wire[63:0] data;wire[7:0] be;
 reg pending=0,response=0;reg[63:0] returned=0;
 wire[31:0] pc,retired;wire[7:0] halt_code;
 assign accept=req && !hold && !pending;
 pace_firmware_cpu #(.EXTERNAL_MMIO(1),.CHECKPOINT_PORT(1),.RETIRE_TIMING(1)) cpu(
  .clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd1),
  .checkpoint_hold(hold),.checkpoint_wr(restore_wr),.checkpoint_index(restore_index),.checkpoint_data(restore_data),
  .io_rdata(32'd0),.io_ready(1'b1),.io_irq(1'b0),
  .mem_req(req),.mem_we(we),.mem_addr(address),.mem_wdata(data),.mem_be(be),
  .mem_accept(accept),.mem_rvalid(response),.mem_rdata(returned),.pc(pc),.retired(retired),.halt_code(halt_code));
 integer lane,i,n,ring_offset;reg [31:0] cursor;
 always @(posedge clk)begin
  response<=0;if(pending)begin pending<=0;response<=1;end
  if(accept)begin
   if(address<29'h06000000 || address>=29'h06200000)$fatal(1,"non RAM access %h",address);
   if(we)begin
    for(lane=0;lane<8;lane=lane+1)if(be[lane])ram[address-29'h06000000][lane*8+:8]<=data[lane*8+:8];
   end else begin returned<=ram[address-29'h06000000];pending<=1;end
  end
 end
 task put(input[23:0] at,input[7:0] value);
 begin ram[at/8][at[2:0]*8+:8]=value;end endtask
 initial begin
  $readmemh("re/fpga_guide_checkpoint/ram64.hex",ram);
  $readmemh("rom/checkpoint_cpu.hex",words);
  for(n=0;n<3;n=n+1)begin
   cursor=32'ha07e4fff-n;ring_offset=12287-n;
   put(24'h7e2000+ring_offset,8'h73);
   put(24'h7e2000+(ring_offset+1)%12288,8'h70);
   put(24'h7e2000+(ring_offset+2)%12288,8'h1b);
   hold=1;reset=1;repeat(4)@(negedge clk);reset=0;
   for(i=32;i<64;i=i+1)words[i]=0;
   words[4]=22;words[5]=cursor;words[29]=32'h807ff000;words[31]=32'h800d35e0;
   words[64]=32'h800044bc;words[65]=1;words[68]=0;
   for(i=0;i<69;i=i+1)begin restore_wr=1;restore_index=i;restore_data=words[i];@(negedge clk);end
   restore_wr=0;hold=0;
   while(pc!=32'h800d35e0)begin @(negedge clk);if(halt_code!=0 || retired>10000)$fatal(1,"native helper fault %h",pc);end
   hold=1;
   if(cpu.gpr[2]!=32'h0000701b)$fatal(1,"native ring length cursor %h got %h",cursor,cpu.gpr[2]);
   $display("Original helper passed cursor %h: section_length bytes %h",cursor,cpu.gpr[2]);
  end
  $display("PASS original guest ring helper: both header bytes wrap, one wraps, neither wraps");$finish;
 end
 initial begin #10000000;$fatal(1,"timeout");end
endmodule
