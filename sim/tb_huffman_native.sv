`timescale 1ns/1ps
// Calls the original 800BECF0 guest function through the actual FPGA CPU.
// This is a function-level conformance test, not a boot checkpoint claim.
module tb_huffman_native;
 reg clk=0,reset=1,hold=1;always #5 clk=~clk;
 reg restore_wr=0;reg[6:0] restore_index=0;reg[31:0] restore_data=0;
 reg[31:0] words[0:68],lengths[0:3];
 reg[7:0] encoded[0:1023],expected[0:1023];
 reg[63:0] ram[0:2097151];
 wire req,we,accept,rv;wire[28:0] address;wire[63:0] data;wire[7:0] be;
 reg pending=0,response=0;reg[63:0] returned=0;
 wire[31:0] pc,retired;wire[7:0] halt_code;
 assign accept=req && !hold && !pending;assign rv=response;
 pace_firmware_cpu #(.EXTERNAL_MMIO(1),.CHECKPOINT_PORT(1),.RETIRE_TIMING(1)) cpu(
  .clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd1),
  .checkpoint_hold(hold),.checkpoint_wr(restore_wr),.checkpoint_index(restore_index),.checkpoint_data(restore_data),
  .io_rdata(32'd0),.io_ready(1'b1),.io_irq(1'b0),
  .mem_req(req),.mem_we(we),.mem_addr(address),.mem_wdata(data),.mem_be(be),
  .mem_accept(accept),.mem_rvalid(rv),.mem_rdata(returned),.pc(pc),.retired(retired),.halt_code(halt_code));
 integer lane,i,n;
 always @(posedge clk)begin
  response<=0;if(pending)begin pending<=0;response<=1;end
  if(accept)begin
   if(address<29'h06000000 || address>=29'h06200000)$fatal(1,"non RAM access %h",address);
   if(we)begin
    for(lane=0;lane<8;lane=lane+1)if(be[lane])ram[address-29'h06000000][lane*8+:8]<=data[lane*8+:8];
   end else begin returned<=ram[address-29'h06000000];pending<=1;end
  end
 end
 initial begin
  $readmemh("re/fpga_guide_checkpoint/ram64.hex",ram);
  $readmemh("rom/checkpoint_cpu.hex",words);
  $readmemh("sim/huffman_vectors/input.hex",encoded);
  $readmemh("sim/huffman_vectors/expected.hex",expected);
  $readmemh("sim/huffman_vectors/lengths.hex",lengths);
  for(i=0;i<1024;i=i+1)begin ram[(24'h200000+i)/8][(i%8)*8+:8]=encoded[i];ram[(24'h210000+i)/8][(i%8)*8+:8]=8'hee;end
  for(n=0;n<4;n=n+1)begin
   hold=1;reset=1;repeat(4)@(negedge clk);reset=0;
   for(i=32;i<64;i=i+1)words[i]=0;
   words[4]=32'h80200000+n*256;words[5]=lengths[n];words[6]=32'h80210000+n*256;words[7]=256;
   words[29]=32'h807ff000;words[31]=32'h800d35e0;words[64]=32'h800becf0;words[65]=1;words[68]=0;
   for(i=0;i<69;i=i+1)begin restore_wr=1;restore_index=i;restore_data=words[i];@(negedge clk);end
   restore_wr=0;hold=0;
   while(pc!=32'h800d35e0)begin
    @(negedge clk);
    if(halt_code!=0 || retired>100000)$fatal(1,"decoder halted PC %h code %h",pc,halt_code);
   end
   hold=1;
   i=0;
   do begin
    if(ram[(24'h210000+n*256+i)/8][(i%8)*8+:8]!=expected[n*256+i])$fatal(1,"native text mismatch case %d byte %d",n,i);
    i=i+1;
   end while(expected[n*256+i-1]!=0);
   $display("Original decoder passed case %d, %d encoded bytes, %d retired",n,lengths[n],retired);
  end
  $display("PASS native firmware Huffman decoder: empty, leading/trailing spaces, phrases, punctuation, long text");$finish;
 end
 initial begin #100000000;$fatal(1,"timeout");end
endmodule
