`ifndef TB_WALL
`define TB_WALL 1
`endif
`ifndef TB_TIMER_PER_RETIRE
`define TB_TIMER_PER_RETIRE 1
`endif
`ifndef TB_COUNT_PER_RETIRE
`define TB_COUNT_PER_RETIRE 0
`endif
`ifndef TB_ICACHE
`define TB_ICACHE 1
`endif
`timescale 1ns/1ps
module tb_guide_transport;
 reg clk=0,reset=1,hold=1;always #5 clk=~clk;
 reg restore_wr=0;reg[6:0] restore_index=0;reg[31:0] restore_data=0;
 reg[31:0] state_words[0:68];
 reg[63:0] ram[0:2097151],flash[0:524287];
 wire cq,cw,ca,cv,gq,gw,ga,gv,tq,ta,tv,dq,da;
 wire[28:0] cad,gad;wire[63:0] cwd,gwd;wire[7:0] cbe,gbe;
 reg[63:0] returned=0;reg response=0,pending=0;reg [1:0] response_owner=0;
 reg [7:0] beats=0,rem=0;reg [28:0] baddr=0;wire [7:0] gburst;
 wire iq,iw,irdy,irq,prdy,device_req,device_ready;wire[31:0] ia,id,ir,pir,dir,retired,pc;wire[1:0] iz;
 wire selected=ia[31:12]==20'hb000a;
 wire config_ready;
 assign device_ready=selected?device_req && config_ready:prdy;
 pace_mmio_response mmio_bus(.clk(clk),.reset(reset),.hold(hold),.cpu_req(iq),
  .cpu_ready(irdy),.cpu_data(ir),.device_req(device_req),.device_ready(device_ready),.device_data(selected?dir:pir));
 reg[63:0] ts_rom[0:62509]; // 500080-byte deterministic SI fixture
 wire[28:0] tad,dad;wire[63:0] dwd;wire[7:0] dbe;
 wire ts_valid,ts_ready,demux_irq;wire[7:0] ts_data;
 wire[31:0] ts_loops,ts_packets,ts_sections,ts_dropped,ts_crc_errors;
 wire[7:0] cpu_halt,model_halt,gpu_error;
 wire gpu_start,gpu_done;wire[31:0] gpu_descriptor,osd_root,gpu_count;
 reg key_valid=0,disable_ts=0;reg[7:0] key=0;
 wire[1:0] owner=gq?2'd1:dq?2'd2:tq?2'd3:2'd0;
 wire bus_req=(gq || dq || tq || cq) && !hold;
 wire[28:0] bus_addr=owner==1?gad:owner==2?dad:owner==3?tad:cad;
 wire bus_write=owner==1?gw:owner==2?1'b1:owner==3?1'b0:cw;
 wire[63:0] bus_data=owner==1?gwd:owner==2?dwd:cwd;
 wire[7:0] bus_be=owner==1?gbe:owner==2?dbe:cbe;
 assign ga=bus_req && owner==1 && !pending;
 assign ca=bus_req && owner==0 && !pending;
 assign da=bus_req && owner==2 && !pending;
 assign ta=bus_req && owner==3 && !pending;
 assign cv=response && response_owner==0;assign gv=response && response_owner==1;assign tv=response && response_owner==3;
 pace_firmware_cpu #(.EXTERNAL_MMIO(1),.CHECKPOINT_PORT(1),.RETIRE_TIMING(1),.WALL_COUNT(`TB_WALL),.COUNT_PER_RETIRE(`TB_COUNT_PER_RETIRE),.ICACHE(`TB_ICACHE)) cpu(
  .clk(clk),.reset(reset),.full_flash_loaded(1'b1),.mmio_policy(2'd1),
  .checkpoint_hold(hold),.checkpoint_wr(restore_wr),.checkpoint_index(restore_index),.checkpoint_data(restore_data),
  .io_req(iq),.io_we(iw),.io_addr(ia),.io_wdata(id),.io_size(iz),.io_rdata(ir),.io_ready(irdy),.io_irq(irq),
  .mem_req(cq),.mem_we(cw),.mem_addr(cad),.mem_wdata(cwd),.mem_be(cbe),.mem_accept(ca),.mem_rvalid(cv),.mem_rdata(returned),
  .pc(pc),.retired(retired),.halt_code(cpu_halt));
 pace_guide_peripherals #(.WALL_TIMER(`TB_WALL),.TIMER_COUNTS_PER_INSTRUCTION(`TB_TIMER_PER_RETIRE)) devices(.clk(clk),.reset(reset),.hold(hold),.retired(retired),
  .io_req(device_req && !selected),.io_we(iw),.io_addr(ia),.io_wdata(id),.io_size(iz),.io_rdata(pir),.io_ready(prdy),.io_irq(irq),
  .key_valid(key_valid),.key_pressed(1'b1),.key_code(key),.gpu_start(gpu_start),.gpu_descriptor(gpu_descriptor),
  .osd_root(osd_root),.gpu_done(gpu_done),.transport_irq(demux_irq),.transport_lock(ts_packets>=3),.model_halt(model_halt));
 pace_guide_blitter gpu(.clk(clk),.reset(reset),.hold(hold),.start(gpu_start),.descriptor(gpu_descriptor),
  .done(gpu_done),.error(gpu_error),.completions(gpu_count),.mem_req(gq),.mem_we(gw),.mem_addr(gad),
  .mem_wdata(gwd),.mem_be(gbe),.mem_burst(gburst),.mem_accept(ga),.mem_rvalid(gv),.mem_rdata(returned));
 pace_ts_replay transport(.clk(clk),.reset(reset),.hold(hold),.enabled(!disable_ts),.length(24'd500080),
  .valid(ts_valid),.ready(ts_ready),.data(ts_data),.loops(ts_loops),
  .mem_req(tq),.mem_addr(tad),.mem_accept(ta),.mem_rvalid(tv),.mem_rdata(returned));
 pace_section_demux demux(.clk(clk),.reset(reset),.hold(hold),.stream_reset(1'b0),
  .ts_valid(ts_valid),.ts_ready(ts_ready),.ts_data(ts_data),
  .io_req(device_req && selected),.io_we(iw),.io_addr(ia),.io_wdata(id),.io_size(iz),.io_rdata(dir),.irq(demux_irq),.config_ready(config_ready),
  .mem_req(dq),.mem_addr(dad),.mem_wdata(dwd),.mem_be(dbe),.mem_accept(da),
  .packets(ts_packets),.sections(ts_sections),.dropped(ts_dropped),.crc_errors(ts_crc_errors));
 integer lane,i,fd;reg[31:0] limit=202000000;reg[31:0] inject_at=0;reg[31:0] key_arg=0;
 reg[31:0] inject2_at=0,key2_arg=0;
 reg[31:0] inject3_at=0,key3_arg=0,inject4_at=0,key4_arg=0;
 integer ring_reads=0,demux_acks=0,trace,decoded=0,title_callbacks=0,row_callbacks=0,title_decodes=0;
 integer nvram_reads=0,favourites_fetches=0,application_loop_fetches=0;
 integer event8_messages=0,k;reg [63:0] cycles=0;integer race_writes=0,hazard_writes=0,cache_ops=0;reg [31:0] hazard_row=0;reg avpid_stack=0,native_trace=0,sec_trace=0,av_trace=0,iow_trace=0,ca_trace=0,io_trace=0,gpu_trace=0,fe_trace=0;reg [31:0] sp_lo=0,sp_hi=0,watch_addr=0;reg [19:0] io_page=20'hb2006;reg [31:0] stack_value;
 reg [31:0] next_progress=225000000;
 reg [31:0] previous_pc=0;string ts_hex="re/transport/diagnostic64.hex",out_prefix="re/transport/native";
 function automatic [31:0] guest_word(input [31:0] address);
  integer b;reg [23:0] a;
  begin
   guest_word=0;a=address[23:0];
   if(address[28:24]==0 && a<=24'hfffffc)
    for(b=0;b<4;b=b+1)guest_word=(guest_word<<8)|{24'd0,ram[(a+b)/8][((a+b)%8)*8+:8]};
  end
 endfunction
 always @(posedge clk)begin
  previous_pc<=pc;if(!hold)cycles<=cycles+1;
  if(pc!=previous_pc)begin
   if(pc==32'h8007fb08 && guest_word(cpu.gpr[6])==32'h08000000 && event8_messages<32)begin
    event8_messages<=event8_messages+1;
    $fdisplay(trace,"SDK_EVENT8 RET %d TARGET %h DATA %h %h %h RA %h WRAPPER_CALLER %h SP %h",retired,cpu.gpr[4],guest_word(cpu.gpr[6]),guest_word(cpu.gpr[6]+4),guest_word(cpu.gpr[6]+8),cpu.gpr[31],guest_word(cpu.gpr[29]+4),cpu.gpr[29]);
    $fflush(trace);
   end
   if(ca_trace)begin
    // Read-only CA/verifier tracing (plusarg +CATRACE): who wakes the ECM/EMM tasks and what they post.
    if(pc==32'h800e7980)$fdisplay(trace,"NDS_SEND RET %d Q %h MSG %h RA %h SP %h",retired,cpu.gpr[4],cpu.gpr[5],cpu.gpr[31],cpu.gpr[29]);
    if(pc==32'h800e79d4)$fdisplay(trace,"NDS_RECV RET %d Q %h RA %h SP %h",retired,cpu.gpr[4],cpu.gpr[31],cpu.gpr[29]);
    if(pc==32'h80051d18)begin
     $fwrite(trace,"POST_MAIN RET %d MSG %h %h %h RA %h SP %h STACK",retired,guest_word(cpu.gpr[4]),guest_word(cpu.gpr[4]+4),guest_word(cpu.gpr[4]+8),cpu.gpr[31],cpu.gpr[29]);
     for(k=0;k<200;k=k+1)begin
      stack_value=guest_word(cpu.gpr[29]+k*4);
      if((stack_value>=32'h80000400 && stack_value<32'h80100000) || (stack_value>=32'h9fc00000 && stack_value<32'h9fe00000))$fwrite(trace," %h",stack_value);
     end
     $fdisplay(trace,"");
    end
   end
   // +NATIVETRACE: every o-code native call (dispatcher 8006E6A8: a0 module, a1 function).
   if(native_trace && pc==32'h8006e6a8)$fdisplay(trace,"NATIVE RET %0d mod %0d fn %h a2 %h a3 %h RA %h",retired,cpu.gpr[4],cpu.gpr[5],cpu.gpr[6],cpu.gpr[7],cpu.gpr[31]);
   // +AVTRACE: A/V manager commands and the driver entry points around them.
   if(av_trace)begin
    if(pc==32'h80055d84)$fdisplay(trace,"AV_DISPATCH RET %0d cmd %h w4 %h w8 %h wc %h RA %h",retired,guest_word(cpu.gpr[4]+32'h20)&32'h00ff0000,guest_word(cpu.gpr[4]+4),guest_word(cpu.gpr[4]+8),guest_word(cpu.gpr[4]+12),cpu.gpr[31]);
    if(pc==32'h8007fb08 && cpu.gpr[4]==guest_word(32'h80106e7c))$fdisplay(trace,"AV_POST RET %0d cmd %h w4 %h w8 %h wc %h RA %h",retired,guest_word(cpu.gpr[6]+32'h20)&32'h00ff0000,guest_word(cpu.gpr[6]+4),guest_word(cpu.gpr[6]+8),guest_word(cpu.gpr[6]+12),cpu.gpr[31]);
    if(pc==32'h80054268)$fdisplay(trace,"AV_SUBMIT_F4 RET %0d RA %h",retired,cpu.gpr[31]);
    if(pc==32'h80054570)$fdisplay(trace,"AV_INIT RET %0d RA %h",retired,cpu.gpr[31]);
    if(pc==32'h8002f44c)$fdisplay(trace,"FE_START_API RET %0d RA %h",retired,cpu.gpr[31]);
   end
   if(fe_trace)begin
    if(pc==32'h80032d0c)$fdisplay(trace,"FE_PUBLISH RET %d status %h RA %h",retired,cpu.gpr[4],cpu.gpr[31]);
    // Frontend stop/tune requests: who asked? (code addresses on the stack)
    if(pc==32'h80032d6c && (cpu.gpr[4]==32'h0e || cpu.gpr[4]==32'h0c))begin
     $fwrite(trace,"DEV20_STACK RET %0d op %h SP %h:",retired,cpu.gpr[4],cpu.gpr[29]);
     for(k=0;k<160;k=k+1)begin
      stack_value=guest_word(cpu.gpr[29]+k*4);
      if(stack_value>=32'h80000400 && stack_value<32'h80100000)$fwrite(trace," %h",stack_value);
     end
     $fdisplay(trace,"");
    end
    if(pc==32'h80032d6c)$fdisplay(trace,"DEV20_CB RET %d op %h arg %h flags %h RA %h",retired,cpu.gpr[4],cpu.gpr[5],cpu.gpr[6],cpu.gpr[31]);
    if(pc==32'h8002f474)$fdisplay(trace,"FE_STOP_API RET %d RA %h",retired,cpu.gpr[31]);
    if(pc==32'h8002f44c)$fdisplay(trace,"FE_START_API RET %d RA %h",retired,cpu.gpr[31]);
    if(pc==32'h8007e6d8)$fdisplay(trace,"DEV_SEND RET %d res %h a1 %h a2 %h a3 %h RA %h",retired,cpu.gpr[4],cpu.gpr[5],cpu.gpr[6],cpu.gpr[7],cpu.gpr[31]);
    if(pc==32'h800284d8)$fdisplay(trace,"FE_POST RET %d cmd %h RA %h",retired,guest_word(cpu.gpr[4]),cpu.gpr[31]);
    if(pc==32'h80028530)$fdisplay(trace,"FE_TASK_START RET %d",retired);
   end
   if(pc==32'h8001ecf8)begin
    $fdisplay(trace,"APPLICATION_ABORT RET %d CODE %h RA %h SP %h",retired,cpu.gpr[4],cpu.gpr[31],cpu.gpr[29]);
    $fflush(trace);dump();$fatal(1,"firmware software abort, code %h, caller %h",cpu.gpr[4],cpu.gpr[31]);
   end
   if(pc==32'h8002926c)nvram_reads<=nvram_reads+1;
   if(io_trace && pc==32'h8002926c)$fdisplay(trace,"NVRAM_READ RET %d A %h %h %h RA %h",retired,cpu.gpr[4],cpu.gpr[5],cpu.gpr[6],cpu.gpr[31]);
   if(pc==32'h80069298)begin
    if(cpu.gpr[2]>=32'h9fc85f41 && cpu.gpr[2]<32'h9fc85f94)favourites_fetches<=favourites_fetches+1;
    if(cpu.gpr[2]==32'h9fc4a538)application_loop_fetches<=application_loop_fetches+1;
   end
   if(pc==32'h800becf0)decoded<=decoded+1;
   if(pc==32'h800c6b42)title_callbacks<=title_callbacks+1;
   if(pc==32'h800c695a)title_decodes<=title_decodes+1;
   if(pc==32'h800cb000)row_callbacks<=row_callbacks+1;
   if(pc==32'h80084008 || pc==32'h80084020 || pc==32'h80083e20)
    $fdisplay(trace,"EVENT RET %d PC %h A %h %h %h %h RA %h",retired,pc,cpu.gpr[4],cpu.gpr[5],cpu.gpr[6],cpu.gpr[7],cpu.gpr[31]);
   if(pc==32'h80084020)
    $fdisplay(trace,"EVENT_DATA RET %d DATA %h %h %h",retired,guest_word(cpu.gpr[5]),guest_word(cpu.gpr[5]+4),guest_word(cpu.gpr[5]+8));
   if(pc==32'h8002a810 || pc==32'h8006e9b0 || pc==32'h80032d0c || pc==32'h80028d5c)
    $fdisplay(trace,"NOTIFY RET %d PC %h A %h %h %h %h RA %h",retired,pc,cpu.gpr[4],cpu.gpr[5],cpu.gpr[6],cpu.gpr[7],cpu.gpr[31]);
   if(pc==32'h80055d84)
    $fdisplay(trace,"AV_COMMAND RET %d DATA %h %h %h %h",retired,guest_word(cpu.gpr[4]),guest_word(cpu.gpr[4]+4),guest_word(cpu.gpr[4]+8),guest_word(cpu.gpr[4]+32));
   if(pc==32'h8007fe1e)
    $fdisplay(trace,"UI_CALLBACK RET %d FN %h A %h %h DATA %h %h %h",retired,cpu.gpr[3],cpu.gpr[4],cpu.gpr[5],guest_word(cpu.gpr[5]),guest_word(cpu.gpr[5]+4),guest_word(cpu.gpr[5]+8));
  end
   if(gpu_trace && cpu.state==2 && !cpu.mips16 && cpu.instruction[31:26]==6'd47 && cache_ops<200)begin cache_ops<=cache_ops+1;
   $fdisplay(trace,"CACHE_OP RET %d PC %h OP %h EA %h",retired,pc,cpu.instruction[20:16],cpu.gpr[cpu.instruction[25:21]]+{{16{cpu.instruction[15]}},cpu.instruction[15:0]});end
 if(gpu_trace && gpu_start)$fdisplay(trace,"GPU_START RET %d DESC %h PC %h",retired,gpu_descriptor,pc);
  if(gpu_trace && gpu.state==4)$fdisplay(trace,"GPU_CMD RET %d OP %h SRC %h EVEN %h ODD %h STRIDE %h XY %h WH %h COL %h",retired,gpu.words[0],gpu.words[1],gpu.words[7],gpu.words[8],gpu.words[11],gpu.words[12],gpu.words[13],gpu.words[14]);
  if(gpu_trace && gpu_done)$fdisplay(trace,"GPU_DONE RET %d",retired);
  response<=0;
  // Multi-beat reads (blitter bursts): one beat per cycle, bus held until done.
  if(pending)begin response<=1;if(beats<=1)pending<=0;else beats<=beats-1'b1;end
  if(response)begin rem<=rem-1'b1;if(rem>1)begin returned<=ram[baddr+1-29'h06000000];baddr<=baddr+1'b1;end end
  if(bus_req && !pending)begin
   if(bus_addr>=29'h06600000 && bus_addr<29'h06600000+62510)begin
    if(bus_write)$fatal(1,"transport ROM write");returned<=ts_rom[bus_addr-29'h06600000];
   end else if(bus_addr>=29'h06400000 && bus_addr<29'h06480000)begin
    if(bus_write)$fatal(1,"flash write");
    returned<=flash[bus_addr-29'h06400000];
   end else if(bus_addr>=29'h06000000 && bus_addr<29'h06200000)begin
    if(bus_write)begin
     for(lane=0;lane<8;lane=lane+1)if(bus_be[lane])ram[bus_addr-29'h06000000][lane*8+:8]<=bus_data[lane*8+:8];
    end else returned<=ram[bus_addr-29'h06000000];
   end else $fatal(1,"unmapped memory %h",bus_addr);
   if(!bus_write)begin pending<=1;response_owner<=owner;beats<=owner==1 ? gburst : 8'd1;rem<=owner==1 ? gburst : 8'd1;baddr<=bus_addr;end
   if(owner==0 && !bus_write && bus_addr>=29'h060f4000 && bus_addr<29'h06100000)ring_reads<=ring_reads+1;
   if(gpu_trace && owner==0 && bus_write && gpu.busy && gpu.copy8 && bus_addr>=29'h06000000+gpu.source[23:3] && bus_addr<29'h06000000+gpu.source[23:3]+29'h800)begin
    race_writes<=race_writes+1;
    hazard_row=((bus_addr-29'h06000000)*8-{5'd0,gpu.source})/gpu.width;
    if(hazard_row>=gpu.row)begin hazard_writes<=hazard_writes+1;if(hazard_writes<40)$fdisplay(trace,"SRC_HAZARD VA %h RET %d PC %h RA %h SRC_ROW %0d BLIT_ROW %0d BLIT_COL %0d XY %h",cpu.bus_virtual,retired,pc,cpu.gpr[31],hazard_row,gpu.row,gpu.dest_index,gpu.words[12]);end
   end
   if(watch_addr!=0 && owner==0 && bus_write && bus_addr==29'h06000000+watch_addr[23:3])
    $fdisplay(trace,"WATCH RET %d PC %h BE %h DATA %h OLD %h RA %h SP %h",retired,pc,bus_be,bus_data,ram[bus_addr-29'h06000000],cpu.gpr[31],cpu.gpr[29]);
   if(owner==0 && bus_write && bus_addr==29'h060860de)
    $fdisplay(trace,"CHANNEL_STATUS RET %d PC %h BE %h DATA %h OLD %h",retired,pc,bus_be,bus_data,ram[bus_addr-29'h06000000]);
  end
  // +IOWRITES: every device write outside the busy demux/timer/serial/I2C/GPU
  // pages, plus all reads of the A/V decoder candidate pages b0002/b0008.
  if(iow_trace && device_req && device_ready &&
     ((iw && ia[31:12]!=20'hb000a && ia[31:12]!=20'hb000d && ia[31:12]!=20'hb2009 && ia[31:12]!=20'hb2006 && ia[31:12]!=20'hb0009) ||
      ia[31:12]==20'hb0002 || ia[31:12]==20'hb0008 ||
      (iw && ia[31:12]==20'hb000a && !(ia[11:0]>=12'h014 && ia[11:0]<12'h094) && ia[11:0]!=12'h124 && ia[11:0]!=12'h128 &&
       ia[11:0]!=12'h144 && ia[11:0]!=12'h148 && ia[11:2]!=10'h02e)))
   $fdisplay(trace,"IOW RET %0d PC %h RA %h WE %0d %h %h READ %h",retired,pc,cpu.gpr[31],iw,ia,id,selected?dir:pir);
  // +SECTRACE: each section the demux completes for a channel (table id) and its outcome.
  if(sec_trace && !hold && demux.state==9)
   $fdisplay(trace,"SECTION RET %0d ch %0d pid %h tid %h len %0d %s",retired,demux.channel,demux.packet_pid,demux.hdr0_c,demux.total_c,
     (!demux.any_match || demux.status[2][demux.channel] || !demux.limit_valid || demux.record_size>demux.ring_free) ? (demux.any_match ? "DROP" : "nomatch") : "DELIVER");
  // +AVPIDSTACK: call stack at every write of the A/V PID registers (B000A094/098/010).
  if(avpid_stack && device_req && device_ready && iw && (ia==32'hb000a094 || ia==32'hb000a098 || ia==32'hb000a010))begin
   $fwrite(trace,"AVPID_STACK RET %0d PC %h RA %h %h=%h SP %h:",retired,pc,cpu.gpr[31],ia,id,cpu.gpr[29]);
   for(k=0;k<200;k=k+1)begin
    stack_value=guest_word(cpu.gpr[29]+k*4);
    if(stack_value>=32'h80000400 && stack_value<32'h80100000 && stack_value[0])$fwrite(trace," %h",stack_value);
   end
   $fdisplay(trace,"");
  end
  if(io_trace && device_req && device_ready && !selected && ia[31:12]==io_page)
   $fdisplay(trace,"I2C RET %d PC %h WE %d %h %h READ %h SP %h",retired,pc,iw,ia,id,pir,cpu.gpr[29]);
  if(ca_trace && device_req && device_ready && ((cpu.gpr[29]>=32'h8012f2c0 && cpu.gpr[29]<32'h80133428) || (cpu.gpr[29]>=sp_lo && cpu.gpr[29]<sp_hi)))
   $fdisplay(trace,"CA_IO RET %d PC %h WE %d %h %h READ %h SP %h",retired,pc,iw,ia,id,pir,cpu.gpr[29]);
  if(device_req && device_ready && selected)begin
   $fdisplay(trace,"RET %d PC %h IO %d %h %h READ %h",retired,pc,iw,ia,id,selected?dir:pir);
   if(iw && ia==32'hb000a0b8)demux_acks<=demux_acks+1;
  end
 end
 task dump;
 begin
  fd=$fopen({out_prefix,"_state.txt"},"w");
  $fdisplay(fd,"TRANSPORT packets %d sections %d CRC %d drops %d guest_ring_reads %d guest_acks %d",ts_packets,ts_sections,ts_crc_errors,ts_dropped,ring_reads,demux_acks);
  $fdisplay(fd,"PARSERS Huffman %d title %d row %d B5 %d OSD %h",decoded,title_callbacks,row_callbacks,title_decodes,osd_root);
  $fdisplay(fd,"APPLICATION NVRAM_READS %d FAVOURITES_FETCHES %d MAIN_LOOP_FETCHES %d",nvram_reads,favourites_fetches,application_loop_fetches);
  $fdisplay(fd,"PC %08x RETIRED %d MODE %d HI %08x LO %08x IRQ %d GPU %d VA %08x",pc,retired,cpu.mips16,cpu.hi,cpu.lo,cpu.interrupt_count,gpu_count,cpu.bus_virtual);
  $fdisplay(fd,"CYCLES %0d ICACHE_HITS %0d TIMER_ACKS %0d SRC_RACE_WRITES %0d HAZARD %0d",cycles,cpu.icache_hits,devices.timer_acks,race_writes,hazard_writes);
  for(i=0;i<32;i=i+1)$fdisplay(fd,"R %d %08x CP0 %08x",i,cpu.gpr[i],cpu.cp0[i]);
  $fdisplay(fd,"TIMER %08x PENDING %d ACK %d KEYFRAMES %d SERIALFRAMES %d",devices.timer_remaining,devices.timer_pending,devices.timer_acks,devices.key_frames,devices.serial_frames);
  $fclose(fd);
  $writememh({out_prefix,"_ram64.hex"},ram);
 end endtask
 initial begin
  if($value$plusargs("LIMIT=%d",limit))begin end
  if($value$plusargs("KEY=%h",key_arg))inject_at=200005000;
  if($value$plusargs("KEY_AT=%d",inject_at))begin end
  if($value$plusargs("KEY2=%h",key2_arg))begin end
  if($value$plusargs("KEY2_AT=%d",inject2_at))begin end
  if($value$plusargs("KEY3=%h",key3_arg))begin end
  if($value$plusargs("KEY3_AT=%d",inject3_at))begin end
  if($value$plusargs("KEY4=%h",key4_arg))begin end
  if($value$plusargs("KEY4_AT=%d",inject4_at))begin end
  disable_ts=$test$plusargs("NO_TS");ca_trace=$test$plusargs("CATRACE");io_trace=$test$plusargs("IOTRACE");iow_trace=$test$plusargs("IOWRITES");av_trace=$test$plusargs("AVTRACE");sec_trace=$test$plusargs("SECTRACE");native_trace=$test$plusargs("NATIVETRACE");avpid_stack=$test$plusargs("AVPIDSTACK");gpu_trace=$test$plusargs("GPUTRACE");fe_trace=$test$plusargs("FETRACE");if($value$plusargs("SPLO=%h",sp_lo))begin end if($value$plusargs("SPHI=%h",sp_hi))begin end if($value$plusargs("WATCH=%h",watch_addr))begin end if($value$plusargs("IOPAGE=%h",io_page))begin end
  $readmemh("re/fpga_guide_checkpoint/ram64.hex",ram);
  $readmemh("re/fpga_guide_checkpoint/flash64.hex",flash);
  $readmemh("rom/checkpoint_cpu.hex",state_words);
  if($value$plusargs("TSHEX=%s",ts_hex))begin end
  $readmemh(ts_hex,ts_rom);
  if($value$plusargs("OUT=%s",out_prefix))begin end
  trace=$fopen({out_prefix,"_mmio.log"},"w");
  repeat(4)@(negedge clk);reset=0;
  for(i=0;i<69;i=i+1)begin restore_wr=1;restore_index=i;restore_data=state_words[i];@(negedge clk);end
  restore_wr=0;repeat(3)@(negedge clk);hold=0;
  while(retired<limit)begin
   @(negedge clk);key_valid=0;
   if(retired>=next_progress)begin
    $display("PROGRESS RET %d GPU %d SECTIONS %d NVRAM_READS %d FAVOURITES_FETCHES %d MAIN_LOOP_FETCHES %d",retired,gpu_count,ts_sections,nvram_reads,favourites_fetches,application_loop_fetches);
    $fflush();next_progress=next_progress+25000000;
   end
   if(inject_at!=0 && retired>=inject_at)begin key_valid=1;key=key_arg[7:0];inject_at=0;end
   if(inject2_at!=0 && retired>=inject2_at)begin key_valid=1;key=key2_arg[7:0];inject2_at=0;end
   if(inject3_at!=0 && retired>=inject3_at)begin key_valid=1;key=key3_arg[7:0];inject3_at=0;end
   if(inject4_at!=0 && retired>=inject4_at)begin key_valid=1;key=key4_arg[7:0];inject4_at=0;end
   if(cpu_halt!=0 || model_halt!=0 || gpu_error!=0)begin
    dump();$fatal(1,"stop PC %h retired %d CPU %h MODEL %h GPU %h",pc,retired,cpu_halt,model_halt,gpu_error);
   end
  end
  dump();$fclose(trace);
  if(!disable_ts && (ts_sections<3 || ring_reads==0 || demux_acks==0))$fatal(1,"guest did not consume transport");
  if(disable_ts && key_arg!=0 && gpu_count<21)$fatal(1,"registered MMIO broke native keyboard/graphics");
  $display("PASS native firmware PC %h RET %d sections %d ring reads %d acks %d",pc,retired,ts_sections,ring_reads,demux_acks);$finish;
 end
 initial begin #60000000000;$fatal(1,"simulation timeout");end
endmodule
