`timescale 1ns/1ps
// BOOT_LOAD=1 equivalence (v0.6.3 Live core): the boot block M10K is filled
// from the flash download instead of being built into the bitstream. One CPU
// uses the initialised ROM (BOOT_LOAD=0, rom/bootloader_words.hex, as v0.6.2);
// the other gets its boot RAM through the load port, fed the flash bytes as
// the MiSTer download delivers them (16-bit writes, low byte first). Both then
// boot the genuine U202 from reset with the I-cache on and a cycle-counted
// timer, and must match on EVERY CLOCK (PC, retired count, RAM and MMIO write
// counts, interrupts) - same memory, same timing.
// Run from project root (needs rom/bootloader_words.hex and sim/fullflash_ddr.hex):
//   iverilog -g2012 -s tb_bootram -o sim/bootram.vvp sim/tb_bootram.sv \
//     rtl/pace_firmware_cpu.sv rtl/pace_bootrom.sv rtl/pace_bootram.sv rtl/pace_muldiv.sv
//   vvp sim/bootram.vvp [+n=INSTRUCTIONS]
module tb_bootram;
  reg clk=0, reset=1;
  always #10 clk=~clk;
  reg [63:0] flash[0:262143];
  initial $readmemh("sim/fullflash_ddr.hex",flash);
  reg [31:0] cycles=0;
  always @(posedge clk) cycles<=cycles+1;
  reg load=0; reg [16:0] load_addr=0; reg [15:0] load_data=0;

  `define PACE_CPU(N, LOADSEL) \
  wire N``_req,N``_we; wire [28:0] N``_addr; wire [63:0] N``_wdata; wire [7:0] N``_be; \
  wire [31:0] N``_pc,N``_ir,N``_ret,N``_rw,N``_lr,N``_ma,N``_md,N``_mr,N``_mc,N``_g; \
  wire [7:0] N``_halt; wire N``_m16,N``_r16; \
  wire N``_accept=N``_req && cycles[1:0]!=0; reg N``_rvalid=0; reg [63:0] N``_rdata=0; \
  reg [63:0] N``_ram[0:2097151]; integer N``_lane; \
  always @(posedge clk) begin \
    N``_rvalid<=0; \
    if(!reset && N``_req && N``_accept) begin \
      if(!((N``_addr>=29'h06000000 && N``_addr<29'h06200000) || (N``_addr>=29'h06400000 && N``_addr<29'h06440000))) \
        $fatal(1,`"N DDR address out of range: %h`",N``_addr); \
      if(N``_we) begin \
        for(N``_lane=0;N``_lane<8;N``_lane=N``_lane+1) \
          if(N``_be[N``_lane]) N``_ram[N``_addr-29'h06000000][N``_lane*8 +:8]<=N``_wdata[N``_lane*8 +:8]; \
      end else begin \
        N``_rdata<=N``_addr>=29'h06400000 ? flash[N``_addr-29'h06400000] : N``_ram[N``_addr-29'h06000000]; \
        N``_rvalid<=1; \
      end \
    end \
  end \
  pace_firmware_cpu #(.EXPERIMENTAL_READY(1),.ICACHE(1),.BOOT_LOAD(LOADSEL)) N ( \
    .clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd1), \
    .boot_load(load),.boot_load_addr(load_addr),.boot_load_data(load_data), \
    .mem_req(N``_req),.mem_we(N``_we),.mem_addr(N``_addr),.mem_wdata(N``_wdata),.mem_be(N``_be), \
    .mem_accept(N``_accept),.mem_rvalid(N``_rvalid),.mem_rdata(N``_rdata), \
    .pc(N``_pc),.instruction(N``_ir),.retired(N``_ret),.ram_writes(N``_rw), \
    .last_ram_address(N``_lr),.last_mmio_address(N``_ma), \
    .last_mmio_value(N``_md),.last_mmio_read(N``_mr), \
    .mmio_writes(N``_mc),.guessed_reads(N``_g),.halt_code(N``_halt), \
    .mips16(N``_m16),.reached_mips16(N``_r16));

  `PACE_CPU(rom, 0)
  `PACE_CPU(ldr, 1)

  integer limit=4000000, k, mismatches=0;
  // flash byte k is lane k%8 of DDR word k/8 (as the download stores it)
  function automatic [7:0] fbyte(input integer k);
    fbyte=flash[k>>3][(k&7)*8 +:8];
  endfunction
  always @(negedge clk) if(!reset) begin
    if(rom_pc!==ldr_pc || rom_ret!==ldr_ret || rom_rw!==ldr_rw || rom_mc!==ldr_mc ||
       rom_ma!==ldr_ma || rom_md!==ldr_md || rom_halt!==ldr_halt ||
       rom.interrupt_count!==ldr.interrupt_count)
      $fatal(1,"FAIL cycle %0d: ROM pc=%h ret=%0d mmio=%0d  LOADED pc=%h ret=%0d mmio=%0d",
             cycles,rom_pc,rom_ret,rom_mc,ldr_pc,ldr_ret,ldr_mc);
  end
  initial begin
    if($value$plusargs("n=%d",limit)) ;
    // the download: 16-bit writes, U202[0:0x20000), in address order
    repeat(3) @(posedge clk);
    for(k=0;k<'h20000;k=k+2) begin
      @(negedge clk); load=1; load_addr=k; load_data={fbyte(k+1),fbyte(k)};
    end
    @(negedge clk); load=0;
    for(k=0;k<32768;k=k+1)
      if(ldr.g_bootram.boot_memory.words[k]!==rom.g_bootrom.boot_memory.words[k]) begin
        if(mismatches<5) $display("boot word %0d: loaded %h rom %h",k,
          ldr.g_bootram.boot_memory.words[k],rom.g_bootrom.boot_memory.words[k]);
        mismatches=mismatches+1;
      end
    if(mismatches) $fatal(1,"FAIL: %0d boot-block words differ after the load",mismatches);
    $display("loaded boot block == rom/bootloader_words.hex (32768 words)");
    @(negedge clk); reset=0;
    wait(rom_halt!=0 || rom_ret>=limit);
    if(rom_halt!=0) $fatal(1,"halt %h at %h",rom_halt,rom_pc);
    $display("PASS: cycle-exact for %0d cycles / %0d instructions; IRQs %0d, MMIO writes %0d, RAM writes %0d",
             cycles,rom_ret,rom.interrupt_count,rom_mc,rom_rw);
    $finish;
  end
endmodule
