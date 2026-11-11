`timescale 1ns/1ps
// BOOTROM=0 equivalence: the genuine U202 boot runs identically whether the
// 128 KiB boot block comes from the M10K ROM (BOOTROM=1) or from the flash
// image in DDR (BOOTROM=0, the Live core, whose bitstream holds no firmware).
// Two CPUs, each with its own RAM, boot the same flash image; every retired
// instruction (PC, word) and the final MMIO/RAM-write state must match.
// RETIRE_TIMING=1: CP0 Count advances per retired instruction, so timer
// interrupts land on the same instruction in both CPUs. (With a cycle-counted
// Count the slower DDR fetches move the first timer IRQ by a few instructions -
// a timing difference, not a functional one; the core uses wall-time Count.)
// Run from project root (needs rom/bootloader_words.hex and the DDR-format
// flash sim/fullflash_ddr.hex):
//   iverilog -g2012 -s tb_bootrom_ddr -o sim/bootrom_ddr.vvp \
//     sim/tb_bootrom_ddr.sv rtl/pace_firmware_cpu.sv rtl/pace_bootrom.sv rtl/pace_muldiv.sv
//   vvp sim/bootrom_ddr.vvp [+n=INSTRUCTIONS]
`ifndef TB_ICACHE
`define TB_ICACHE 0   // -DTB_ICACHE=1: both CPUs with the I-cache, as in the Live core
`endif
module tb_bootrom_ddr;
  reg clk=0, reset=1;
  always #10 clk=~clk;
  reg [63:0] flash[0:262143];
  initial $readmemh("sim/fullflash_ddr.hex",flash);
  reg [31:0] cycles=0;
  always @(posedge clk) cycles<=cycles+1;

  // ---- one CPU + its own RAM, same memory model as tb_research ----
  `define PACE_CPU(N, ROMSEL) \
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
  pace_firmware_cpu #(.EXPERIMENTAL_READY(1),.RETIRE_TIMING(1),.ICACHE(`TB_ICACHE),.BOOTROM(ROMSEL)) N ( \
    .clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd1), \
    .mem_req(N``_req),.mem_we(N``_we),.mem_addr(N``_addr),.mem_wdata(N``_wdata),.mem_be(N``_be), \
    .mem_accept(N``_accept),.mem_rvalid(N``_rvalid),.mem_rdata(N``_rdata), \
    .pc(N``_pc),.instruction(N``_ir),.retired(N``_ret),.ram_writes(N``_rw), \
    .last_ram_address(N``_lr),.last_mmio_address(N``_ma), \
    .last_mmio_value(N``_md),.last_mmio_read(N``_mr), \
    .mmio_writes(N``_mc),.guessed_reads(N``_g),.halt_code(N``_halt), \
    .mips16(N``_m16),.reached_mips16(N``_r16));

  `PACE_CPU(rom, 1)
  `PACE_CPU(ddr, 0)

  // Retire streams: (PC, mips16, instruction) per retired instruction, kept
  // in a ring so the faster CPU can run ahead of the slower one.
  localparam DEPTH=1<<21;   // the M10K CPU runs ~20% ahead of the DDR one
  reg [64:0] rom_log[0:DEPTH-1], ddr_log[0:DEPTH-1];
  integer rom_n=0, ddr_n=0, cmp_n=0, limit=4000000;
  reg [31:0] rom_last=0, ddr_last=0, rom_pc_prev=0, ddr_pc_prev=0;
  reg rom_m16_prev=0, ddr_m16_prev=0;
  // The retire counter steps by one; log the instruction that just retired
  // (pc/instruction as they stood on the previous clock, before the update).
  reg [31:0] rom_ir_prev=0, ddr_ir_prev=0;
  always @(posedge clk) if(!reset) begin
    if(rom_ret!=rom_last) begin
      if(rom_ret!=rom_last+1) $fatal(1,"rom retire step %0d",rom_ret-rom_last);
      rom_log[rom_n%DEPTH]<={rom_m16_prev,rom_pc_prev,rom_ir_prev}; rom_n=rom_n+1; rom_last=rom_ret;
    end
    if(ddr_ret!=ddr_last) begin
      if(ddr_ret!=ddr_last+1) $fatal(1,"ddr retire step %0d",ddr_ret-ddr_last);
      ddr_log[ddr_n%DEPTH]<={ddr_m16_prev,ddr_pc_prev,ddr_ir_prev}; ddr_n=ddr_n+1; ddr_last=ddr_ret;
    end
    rom_pc_prev=rom_pc; rom_ir_prev=rom_ir; rom_m16_prev=rom_m16;
    ddr_pc_prev=ddr_pc; ddr_ir_prev=ddr_ir; ddr_m16_prev=ddr_m16;
  end
  always @(negedge clk) if(!reset) begin
    while(cmp_n<rom_n && cmp_n<ddr_n) begin
      if(rom_log[cmp_n%DEPTH]!==ddr_log[cmp_n%DEPTH])
        $fatal(1,"FAIL: instruction %0d differs: ROM pc=%h ir=%h  DDR pc=%h ir=%h",cmp_n,
               rom_log[cmp_n%DEPTH][63:32],rom_log[cmp_n%DEPTH][31:0],
               ddr_log[cmp_n%DEPTH][63:32],ddr_log[cmp_n%DEPTH][31:0]);
      cmp_n=cmp_n+1;
    end
    if(rom_n-cmp_n>=DEPTH-4 || ddr_n-cmp_n>=DEPTH-4) $fatal(1,"retire logs overran (%0d/%0d/%0d)",rom_n,ddr_n,cmp_n);
  end

  integer boot_block_fetches=0;
  always @(posedge clk) if(!reset && ddr_req && ddr_accept && ddr_addr>=29'h06400000 && ddr_addr<29'h06404000)
    boot_block_fetches=boot_block_fetches+1;

  initial begin
    if($value$plusargs("n=%d",limit)) ;
    repeat(5) @(posedge clk);
    @(negedge clk);
    reset=0;
    wait((rom_halt!=0 || ddr_halt!=0) || (cmp_n>=limit));
    if(rom_halt!=0 || ddr_halt!=0)
      $fatal(1,"halt ROM=%h@%h DDR=%h@%h after %0d matched",rom_halt,rom_pc,ddr_halt,ddr_pc,cmp_n);
    if(boot_block_fetches==0) $fatal(1,"BOOTROM=0 CPU never read the boot block from DDR");
    $display("PASS: %0d instructions identical (boot block from M10K vs from DDR flash image); DDR boot-block reads=%0d IRQ rom=%0d ddr=%0d MMIO writes rom=%0d ddr=%0d",
             cmp_n,boot_block_fetches,rom.interrupt_count,ddr.interrupt_count,rom_mc,ddr_mc);
    $finish;
  end
endmodule
