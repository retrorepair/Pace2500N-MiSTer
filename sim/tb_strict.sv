`timescale 1ns/1ps
// Full strict boot regression with 16 MiB RAM and request backpressure.
// Run from project root; compile with pace_firmware_cpu.sv + pace_bootrom.sv.
// This models the CPU memory interface, not the MiSTer DDR controller/upload.
module tb_strict;
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
  wire accept; reg rvalid=0;
  reg [63:0] rdata=0;
  reg [63:0] ram[0:2097151];
  reg [31:0] cycles=0;
  integer lane;
  assign accept=req && cycles[1:0]!=0;
  always @(posedge clk) begin
    cycles<=cycles+1;
    rvalid<=0;
    if(!reset && req && accept) begin
      if(addr<29'h06000000 || addr>=29'h06200000)
        $fatal(1,"DDR address out of RAM range: %h",addr);
      if(we) begin
        for(lane=0;lane<8;lane=lane+1)
          if(be[lane]) ram[addr-29'h06000000][lane*8 +:8]<=wdata[lane*8 +:8];
      end else begin
        rdata<=ram[addr-29'h06000000];
        rvalid<=1;
      end
    end
  end
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
    wait(halt!=0 || retired>=3200000);
    if(halt!==8'h03 || pc!==32'hbfc01e1c || last_mmio_read!==32'hb0000012 || !reach16)
      $fatal(1,"Strict endpoint differs: halt=%h pc=%h read=%h m16=%b retired=%d",halt,pc,last_mmio_read,reach16,retired);
    // Python starts at offset 8; HDL additionally retires two leading NOPs.
    if(retired!==32'd3178988 || ram_writes!==32'd1770706 || mmio_count!==32'd12 || checked!=7)
      $fatal(1,"Strict execution counters differ");
    $display("PASS: strict firmware endpoint PC=%h retired=%d RAM writes=%d MMIO writes=%d",pc,retired,ram_writes,mmio_count);
    $finish;
  end
  // Sample after the CPU's nonblocking updates; validate every write in order.
  always @(negedge clk) if(!reset) begin

    if(checked<7 && mmio_count!=checked) begin
      if(mmio_count!=checked+1 || checked>=7)
        $fatal(1,"Unexpected MMIO count %d",mmio_count);
      if(mmio_address!==expected_address[checked] || mmio_data!==expected_data[checked])
        $fatal(1,"MMIO write %d differs: %h %h",checked+1,mmio_address,mmio_data);
      checked=checked+1;
    end
  end
  initial begin #1000000000; $fatal(1,"CPU test timeout"); end
endmodule
