`timescale 1ns/1ps
module tb_guide_resume;
 reg clk=0,reset=1,hold=1;always #5 clk=~clk;
 reg restore_wr=0;reg[6:0] restore_index=0;reg[31:0] restore_data=0;
 reg[31:0] state_words[0:68];
 reg[63:0] ram[0:2097151],flash[0:524287];
 wire cq,cw,ca,cv,gq,gw,ga,gv;
 wire[28:0] cad,gad;wire[63:0] cwd,gwd;wire[7:0] cbe,gbe;
 reg[63:0] returned=0;reg response=0,response_gpu=0,pending=0;
 wire iq,iw,irdy,irq;wire[31:0] ia,id,ir,retired,pc;wire[1:0] iz;
 wire[7:0] cpu_halt,model_halt,gpu_error;
 wire gpu_start,gpu_done;wire[31:0] gpu_descriptor,osd_root,gpu_count;
 reg key_valid=0;reg[7:0] key=0;
 wire choose_gpu=gq;
 wire bus_req=(choose_gpu?gq:cq) && !hold;
 wire[28:0] bus_addr=choose_gpu?gad:cad;
 wire bus_write=choose_gpu?gw:cw;
 wire[63:0] bus_data=choose_gpu?gwd:cwd;
 wire[7:0] bus_be=choose_gpu?gbe:cbe;
 assign ga=bus_req && choose_gpu && !pending;
 assign ca=bus_req && !choose_gpu && !pending;
 assign cv=response && !response_gpu;assign gv=response && response_gpu;
 pace_firmware_cpu #(.EXTERNAL_MMIO(1),.CHECKPOINT_PORT(1),.RETIRE_TIMING(1)) cpu(
  .clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd1),
  .checkpoint_hold(hold),.checkpoint_wr(restore_wr),.checkpoint_index(restore_index),.checkpoint_data(restore_data),
  .io_req(iq),.io_we(iw),.io_addr(ia),.io_wdata(id),.io_size(iz),.io_rdata(ir),.io_ready(irdy),.io_irq(irq),
  .mem_req(cq),.mem_we(cw),.mem_addr(cad),.mem_wdata(cwd),.mem_be(cbe),.mem_accept(ca),.mem_rvalid(cv),.mem_rdata(returned),
  .pc(pc),.retired(retired),.halt_code(cpu_halt));
 pace_guide_peripherals devices(.clk(clk),.reset(reset),.hold(hold),.retired(retired),
  .io_req(iq),.io_we(iw),.io_addr(ia),.io_wdata(id),.io_size(iz),.io_rdata(ir),.io_ready(irdy),.io_irq(irq),
  .key_valid(key_valid),.key_pressed(1'b1),.key_code(key),.gpu_start(gpu_start),.gpu_descriptor(gpu_descriptor),
  .osd_root(osd_root),.gpu_done(gpu_done),.transport_irq(1'b0),.transport_lock(1'b0),.model_halt(model_halt));
 pace_guide_blitter gpu(.clk(clk),.reset(reset),.hold(hold),.start(gpu_start),.descriptor(gpu_descriptor),
  .done(gpu_done),.error(gpu_error),.completions(gpu_count),.mem_req(gq),.mem_we(gw),.mem_addr(gad),
  .mem_wdata(gwd),.mem_be(gbe),.mem_accept(ga),.mem_rvalid(gv),.mem_rdata(returned));
 integer lane,i,fd;reg[31:0] limit=200100000;reg[31:0] inject_at=0;reg[31:0] key_arg=0;
 always @(posedge clk)begin
  response<=0;
  if(pending)begin pending<=0;response<=1;end
  if(bus_req && !pending)begin
   if(bus_addr>=29'h06400000 && bus_addr<29'h06480000)begin
    if(bus_write)$fatal(1,"flash write");
    returned<=flash[bus_addr-29'h06400000];
   end else if(bus_addr>=29'h06000000 && bus_addr<29'h06200000)begin
    if(bus_write)begin
     for(lane=0;lane<8;lane=lane+1)if(bus_be[lane])ram[bus_addr-29'h06000000][lane*8+:8]<=bus_data[lane*8+:8];
    end else returned<=ram[bus_addr-29'h06000000];
   end else $fatal(1,"unmapped memory %h",bus_addr);
   if(!bus_write)begin pending<=1;response_gpu<=choose_gpu;end
  end
 end
 task dump;
 begin
  fd=$fopen("re/fpga_guide_checkpoint/rtl_state.txt","w");
  $fdisplay(fd,"PC %08x RETIRED %d MODE %d HI %08x LO %08x IRQ %d GPU %d VA %08x",pc,retired,cpu.mips16,cpu.hi,cpu.lo,cpu.interrupt_count,gpu_count,cpu.bus_virtual);
  for(i=0;i<32;i=i+1)$fdisplay(fd,"R %d %08x CP0 %08x",i,cpu.gpr[i],cpu.cp0[i]);
  $fdisplay(fd,"TIMER %08x PENDING %d ACK %d KEYFRAMES %d SERIALFRAMES %d",devices.timer_remaining,devices.timer_pending,devices.timer_acks,devices.key_frames,devices.serial_frames);
  $fclose(fd);
  $writememh("re/fpga_guide_checkpoint/rtl_ram64.hex",ram);
 end endtask
 initial begin
  if($value$plusargs("LIMIT=%d",limit))begin end
  if($value$plusargs("KEY=%h",key_arg))inject_at=200005000;
  $readmemh("re/fpga_guide_checkpoint/ram64.hex",ram);
  $readmemh("re/fpga_guide_checkpoint/flash64.hex",flash);
  $readmemh("rom/checkpoint_cpu.hex",state_words);
  repeat(4)@(negedge clk);reset=0;
  for(i=0;i<69;i=i+1)begin restore_wr=1;restore_index=i;restore_data=state_words[i];@(negedge clk);end
  restore_wr=0;repeat(3)@(negedge clk);hold=0;
  while(retired<limit)begin
   @(negedge clk);key_valid=0;
   if(inject_at!=0 && retired>=inject_at)begin key_valid=1;key=key_arg[7:0];inject_at=0;end
   if(cpu_halt!=0 || model_halt!=0 || gpu_error!=0)begin
    dump();$fatal(1,"stop PC %h retired %d CPU %h MODEL %h GPU %h",pc,retired,cpu_halt,model_halt,gpu_error);
   end
  end
  dump();$display("DONE PC %h retired %d GPU %d",pc,retired,gpu_count);$finish;
 end
 initial begin #15000000000;$fatal(1,"simulation timeout");end
endmodule
