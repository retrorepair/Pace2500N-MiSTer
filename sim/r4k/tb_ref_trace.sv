`timescale 1ns/1ps
// Reference architectural trace of the current CPU (pace_firmware_cpu) booting the real U202
// from reset: one line per retired instruction, "index pc mode reg value" (reg 0 = no register
// written), plus MMIO accesses "M R|W addr size value". Device reads return 0 (mmio_policy 1).
// The new CPU's bench (sim/r4k) is compared against this file.
// Run from project root (needs rom/bootloader_words.hex, sim/fullflash_ddr.hex):
//   iverilog -g2012 -s tb_ref_trace -o sim/r4k/ref.vvp sim/r4k/tb_ref_trace.sv rtl/pace_firmware_cpu.sv \
//     rtl/pace_bootrom.sv rtl/pace_bootram.sv rtl/pace_muldiv.sv
//   vvp sim/r4k/ref.vvp +n=INSTRUCTIONS +out=sim/r4k/ref_trace.txt
module tb_ref_trace;
  reg clk=0, reset=1;
  always #10 clk=~clk;
  reg [63:0] flash[0:262143];
  initial $readmemh("sim/fullflash_ddr.hex",flash);
  reg [31:0] cycles=0;
  always @(posedge clk) cycles<=cycles+1;
  wire req,we; wire [28:0] addr; wire [63:0] wdata; wire [7:0] be;
  wire [31:0] pc,ir,ret,rw,lr,ma,md,mr,mc,g; wire [7:0] halt; wire m16,r16;
  wire accept=req && cycles[1:0]!=0; reg rvalid=0; reg [63:0] rdata=0;
  reg [63:0] ram[0:2097151]; integer lane;
  always @(posedge clk) begin
    rvalid<=0;
    if(!reset && req && accept) begin
      if(we) begin
        for(lane=0;lane<8;lane=lane+1) if(be[lane]) ram[addr-29'h06000000][lane*8 +:8]<=wdata[lane*8 +:8];
      end else begin
        rdata<=addr>=29'h06400000 ? flash[addr-29'h06400000] : ram[addr-29'h06000000];
        rvalid<=1;
      end
    end
  end
  pace_firmware_cpu #(.EXPERIMENTAL_READY(1),.ICACHE(1)) cpu (
    .clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd1),
    .boot_load(1'b0),.boot_load_addr(17'd0),.boot_load_data(16'd0),
    .mem_req(req),.mem_we(we),.mem_addr(addr),.mem_wdata(wdata),.mem_be(be),
    .mem_accept(accept),.mem_rvalid(rvalid),.mem_rdata(rdata),
    .pc(pc),.instruction(ir),.retired(ret),.ram_writes(rw),
    .last_ram_address(lr),.last_mmio_address(ma),.last_mmio_value(md),.last_mmio_read(mr),
    .mmio_writes(mc),.guessed_reads(g),.halt_code(halt),.mips16(m16),.reached_mips16(r16));
  integer fd, limit=200000, first16=-1;
  reg [31:0] prev_pc=32'hbfc00000, prev_ret=0, prev_mc=0, prev_g=0; reg prev_m16=0;
  reg [8*256-1:0] out;
  always @(posedge clk) if(!reset) begin
    // gw_* hold the register write of the instruction that retires on this edge
    if(ret!=prev_ret) begin
      $fdisplay(fd,"%0d %h %0d %0d %h",prev_ret,prev_pc,prev_m16,cpu.gw_en ? cpu.gw_idx : 5'd0,cpu.gw_en ? cpu.gw_val : 32'd0);
      if(prev_m16 && first16<0) first16=prev_ret;
    end
    if(mc!=prev_mc) $fdisplay(fd,"M W %h %0d %h",ma,cpu.load_size,md);
    if(g!=prev_g) $fdisplay(fd,"M R %h %0d 0",mr,cpu.load_size);
    prev_ret<=ret; prev_pc<=pc; prev_m16<=m16; prev_mc<=mc; prev_g<=g;
  end
  // +dump=K: at the boundary before instruction index K, write the architectural state as
  // the Live core's STATE.bin layout (one hex word per line: 0-31 GPR, 32-63 CP0, 64 PC,
  // 65 MIPS16, 66 HI, 67 LO) and RAM (DDR words) for the new CPU's bench to start from.
  integer dump_at=-1, dfd, di; reg dumped=0;
  reg [8*256-1:0] dump_state, dump_ram;
  always @(negedge clk) if(!reset && !dumped && dump_at>=0 && ret==dump_at && cpu.state==0 &&
                           !cpu.branch_pending && !cpu.m16_extended) begin
    dfd=$fopen(dump_state,"w");
    for(di=0;di<32;di=di+1) $fdisplay(dfd,"%h",cpu.gpr[di]);
    for(di=0;di<32;di=di+1) $fdisplay(dfd,"%h",cpu.cp0[di]);
    $fdisplay(dfd,"%h",pc); $fdisplay(dfd,"%h",{31'd0,m16}); $fdisplay(dfd,"%h",cpu.hi); $fdisplay(dfd,"%h",cpu.lo);
    $fclose(dfd);
    $writememh(dump_ram,ram);
    $display("dumped state before instruction %0d: pc %h mips16 %0d", ret, pc, m16);
    dumped=1;
  end
  initial begin
    if(!$value$plusargs("dump=%d",dump_at)) dump_at=-1;
    if(!$value$plusargs("dumpstate=%s",dump_state)) dump_state="sim/r4k/state.hex";
    if(!$value$plusargs("dumpram=%s",dump_ram)) dump_ram="sim/r4k/ram.hex";
    if(!$value$plusargs("out=%s",out)) out="sim/r4k/ref_trace.txt";
    if($value$plusargs("n=%d",limit)) ;
    fd=$fopen(out,"w");
    repeat(3) @(posedge clk); @(negedge clk); reset=0;
    wait(halt!=0 || ret>=limit);
    if(halt!=0) $display("halt %h at %h",halt,pc);
    $display("reference: %0d instructions, %0d cycles, first MIPS16 at index %0d, IRQs %0d, MMIO writes %0d",
             ret,cycles,first16,cpu.interrupt_count,mc);
    $fclose(fd); $finish;
  end
endmodule
