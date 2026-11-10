`timescale 1ns/1ps
// Quartus testbench for early genuine Pace bootloader initialization.
// Simulate in project root: iverilog -g2012 -s tb_boot -o boot.vvp \
//     sim/tb_boot.sv rtl/pace_firmware_cpu.sv rtl/pace_bootrom.sv
// Then run: vvp boot.vvp
module tb_boot;
  reg clk=0, reset=1;
  always #10 clk=~clk;
  wire req,we;wire [28:0] addr;
  wire [63:0] wdata;wire [7:0] be;
  wire [31:0] pc,instruction,retired,ram_writes,last_ram,
              mmio_address,mmio_data,last_mmio_read,mmio_count,guessed;
  wire [7:0] halt;
  wire m16,reach16;
  reg [31:0] expected_address [0:6];
  reg [31:0] expected_data [0:6];
  integer checked=0;
  reg accept=0,rvalid=0;
  reg [63:0] rdata=0;
  // No DDR transaction should be needed for the initial seven register writes.
  pace_firmware_cpu DUT (
    .clk(clk),.reset(reset),.full_flash_loaded(1'b0),.mmio_policy(2'd0),
    .mem_req(req),.mem_we(we),.mem_addr(addr),.mem_wdata(wdata),.mem_be(be),
    .mem_accept(accept),.mem_rvalid(rvalid),.mem_rdata(rdata),
    .pc(pc),.instruction(instruction),.retired(retired),.ram_writes(ram_writes),
    .last_ram_address(last_ram),.last_mmio_address(mmio_address),
    .last_mmio_value(mmio_data),.last_mmio_read(last_mmio_read),
    .mmio_writes(mmio_count),.guessed_reads(guessed),.halt_code(halt),
    .mips16(m16),.reached_mips16(reach16)
  );
  initial begin
    expected_address[0]=32'hb0000430; expected_data[0]=32'h40000021;
    expected_address[1]=32'hb0000440; expected_data[1]=32'h00000141;
    expected_address[2]=32'hb0000410; expected_data[2]=32'h00000001;
    expected_address[3]=32'hb0000400; expected_data[3]=32'h00000023;
    expected_address[4]=32'hb0000600; expected_data[4]=32'h00000200;
    expected_address[5]=32'hb0000610; expected_data[5]=32'h00232323;
    expected_address[6]=32'hb2006000; expected_data[6]=32'h00000080;
    repeat(5) @(posedge clk);
    @(negedge clk);
    reset=0;
    wait(checked==7 || halt!=0 || retired>=300);
    if(halt!=0)$fatal(1,"Premature halt code %h PC=%h",halt,pc);
    if(mmio_count!=7)$fatal(1,"Did not reach 7 original NEC register writes");
    if(mmio_address!==32'hb2006000 || mmio_data!==32'h00000080)
      $fatal(1,"Real firmware's seventh MMIO differs: %h %h",mmio_address,mmio_data);
    $display("PASS: original U202 ROM executes seven genuine MMIO setup writes, PC=%h retired=%d",pc,retired);
    $finish;
  end
  // Sample after the CPU's nonblocking updates; validate every write in order.
  always @(negedge clk) if(!reset) begin
    if(req) $fatal(1,"Unexpected DDR request before initial MMIO sequence");
    if(mmio_count!=checked) begin
      if(mmio_count!=checked+1 || checked>=7)
        $fatal(1,"Unexpected MMIO count %d",mmio_count);
      if(mmio_address!==expected_address[checked] || mmio_data!==expected_data[checked])
        $fatal(1,"MMIO write %d differs: %h %h",checked+1,mmio_address,mmio_data);
      checked=checked+1;
    end
  end
  initial begin #300000; $fatal(1,"CPU test timeout"); end
endmodule
