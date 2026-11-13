// System simulation (Verilator) of the v0.7.0 CPU in its real surroundings: rtl/pace_r4k.sv
// (the wrapper, with rtl/r4k converted to Verilog by sim/vl/synth.sh), the EMMA device
// registers, blitter, section demux and MPEG status, wired as rtl/Pace2500N_Transport.sv
// wires them, on a DDR model with the top level's arbiter. It resumes the Guide from the
// Live core's checkpoint (RAM.bin / STATE.bin as hex) with no transport stream.
//
// Output (+log=FILE, may be a named pipe): the stream sim/vl/tb_shadow.sv replays into the
// old CPU to find the first instruction where the two differ.
//   R pc rd data     retired instruction: pc (bit 0 = MIPS16), rd = {write enable, register}
//   X epc cause      the next R is the first instruction of an interrupt (ExcCode 0) handler
//   M w addr size v  device register access seen by the CPU (v = value read or written)
//   D addr be data   a RAM write by a device (blitter, demux), DDR word address
// Plusargs: +ram=HEX +state=HEX +flash=HEX +log=FILE +cycles=N (clk_sys) +key=HH +keyat=N
//           +status=N (print a status line every N clk_sys cycles) +lat=N (DDR read latency)
`timescale 1ps/1ps
module tb_sys;
    // 75 MHz core clock, 37.5 MHz memory-side clock (rising edges aligned), 50 MHz clk_sys.
    reg clk2x = 0, clk1x = 0, clk_sys = 0;
    initial forever begin   // 13.333 ns per clk2x cycle
        #6667 clk2x = 1; clk1x = 1;
        #6666 clk2x = 0;
        #6667 clk2x = 1; clk1x = 0;
        #6666 clk2x = 0;
    end
    initial begin #1700; forever #10000 clk_sys = ~clk_sys; end

    reg core_reset = 1, holding = 1, loaded_state = 0;
    reg state_write = 0; reg [6:0] state_index = 0; reg [31:0] state_data = 0;
    reg [31:0] state_words [0:68];
    reg [63:0] ram [0:2097151];
    reg [63:0] flash [0:262143];

    // ---------------------------------------------------------------- the system
    wire cq, cw, ca, cv, gq, gw, ga, gv, dq, da;
    wire [28:0] cad, gad, dad;
    wire [63:0] cwd, gwd, dwd; wire [7:0] cbe, gbe, dbe, cburst, gburst;
    wire iq, iw, irdy, irq, prdy, device_req, device_ready;
    wire [31:0] ia, id, ir, pir, dir; wire [1:0] iz;
    wire [31:0] pc, retired; wire [5:0] cpu_errors; wire [31:0] cpu_unmapped;
    wire [31:0] dbg_fetch_stall, dbg_cached_stall, dbg_mem_stall, dbg_exceptions, dbg_cause, dbg_epc, dbg_badvaddr;
    wire trace_frozen; wire [511:0] trace_page_data;
    wire mpeg_hit, mpeg_irq; wire [31:0] mpeg_rdata;
    wire demux_selected = ia[31:12] == 20'hb000a;
    wire demux_config_ready, demux_irq;
    assign device_ready = demux_selected ? device_req && demux_config_ready : prdy;
    reg key_valid = 0; reg [7:0] key_code = 0;
    wire gpu_start, gpu_done, gpu_busy; wire [31:0] gpu_descriptor, osd_root, gpu_count, gpu_last;
    wire [7:0] model_halt, gpu_error, last_key;
    wire [31:0] serial_frames, key_frames, timer_acks, gpu_acks;
    reg [63:0] DDRAM_DOUT = 0; reg DDRAM_DOUT_READY = 0;
    // transport stream (+ts=FILE, looped; +tsgap=N clk_sys cycles per byte, default 50 = 8 Mbit/s)
    reg ts_valid = 0; reg [7:0] ts_byte = 0; wire ts_ready; wire [31:0] ts_packets;
    integer tsfd = 0, tsgap = 50, tswait = 0, tsc;

    pace_r4k #(.COUNT_NUM(27), .COUNT_DEN(100)) cpu (.clk_sys(clk_sys), .clk1x(clk1x), .clk2x(clk2x),
        .reset_sys(core_reset), .hold_sys(holding), .ckpt_loaded(loaded_state),
        .state_wr(state_write), .state_index(state_index), .state_data(state_data), .io_irq(irq),
        .ddr_req(cq), .ddr_we(cw), .ddr_addr(cad), .ddr_wdata(cwd), .ddr_be(cbe), .ddr_burst(cburst),
        .ddr_accept(ca), .ddr_rvalid(cv), .ddr_rdata(DDRAM_DOUT),
        .io_req(iq), .io_we(iw), .io_addr(ia), .io_wdata(id), .io_size(iz), .io_rdata(ir), .io_ready(irdy),
        .pc(pc), .retired(retired), .errors(cpu_errors), .unmapped(cpu_unmapped),
        .dbg_fetch_stall(dbg_fetch_stall), .dbg_cached_stall(dbg_cached_stall), .dbg_mem_stall(dbg_mem_stall),
        .dbg_exceptions(dbg_exceptions), .dbg_cause(dbg_cause), .dbg_epc(dbg_epc), .dbg_badvaddr(dbg_badvaddr),
        .trace_next(1'b0), .trace_page_data(trace_page_data), .trace_trigger(1'b0), .trace_frozen(trace_frozen));
    pace_mmio_response mmio_bus (.clk(clk_sys), .reset(core_reset), .hold(holding), .cpu_req(iq),
        .cpu_ready(irdy), .cpu_data(ir), .device_req(device_req), .device_ready(device_ready),
        .device_data(demux_selected ? dir : mpeg_hit ? mpeg_rdata : pir));
    pace_guide_peripherals devices (.clk(clk_sys), .reset(core_reset), .hold(holding), .retired(retired),
        .io_req(device_req && !demux_selected), .io_we(iw), .io_addr(ia), .io_wdata(id), .io_size(iz),
        .io_rdata(pir), .io_ready(prdy), .io_irq(irq),
        .key_valid(key_valid), .key_pressed(1'b1), .key_code(key_code), .gpu_start(gpu_start),
        .gpu_descriptor(gpu_descriptor), .osd_root(osd_root), .gpu_done(gpu_done),
        .transport_irq(demux_irq), .mpeg_irq(mpeg_irq), .transport_lock(ts_packets >= 3), .model_halt(model_halt),
        .serial_frames(serial_frames), .key_frames(key_frames), .timer_acks(timer_acks),
        .gpu_acks(gpu_acks), .last_key(last_key));
    pace_guide_blitter gpu (.clk(clk_sys), .reset(core_reset), .hold(holding), .start(gpu_start),
        .descriptor(gpu_descriptor), .done(gpu_done), .busy(gpu_busy), .error(gpu_error),
        .completions(gpu_count), .last_opcode(gpu_last),
        .mem_req(gq), .mem_we(gw), .mem_addr(gad), .mem_wdata(gwd), .mem_be(gbe), .mem_burst(gburst),
        .mem_accept(ga), .mem_rvalid(gv), .mem_rdata(DDRAM_DOUT));
    pace_section_demux demux (.clk(clk_sys), .reset(core_reset), .stream_reset(1'b0), .hold(holding),
        .ts_valid(ts_valid), .ts_ready(ts_ready), .ts_data(ts_byte),
        .io_req(device_req && demux_selected), .io_we(iw), .io_addr(ia), .io_wdata(id), .io_size(iz),
        .io_rdata(dir), .irq(demux_irq), .config_ready(demux_config_ready),
        .mem_req(dq), .mem_addr(dad), .mem_wdata(dwd), .mem_be(dbe), .mem_accept(da),
        .packets(ts_packets), .sections(), .dropped(), .crc_errors(), .av_video(), .av_audio(), .av_pcr());
    pace_mpeg_status mpeg_status (.clk(clk_sys), .reset(core_reset),
        .access(device_req && device_ready && !holding && !demux_selected), .we(iw), .addr(ia), .wdata(id),
        .hit(mpeg_hit), .rdata(mpeg_rdata), .irq(mpeg_irq),
        .seq_evt(1'b0), .gop_evt(1'b0), .pic_evt(1'b0), .field_evt(1'b0),
        .seq_hsize(12'd0), .seq_vsize(12'd0), .seq_aspect(4'd0), .gop_time_code(23'd0), .pic_structure(2'd0));

    // ------------------------------------------- DDR arbiter (as the top level) and model
    integer lat = 6, latrand = 0, busypct = 0;   // +latrand=N: 0..N extra cycles per read; +busy=P: DDR busy P% of cycles
    reg ddr_busy = 0;
    always @(posedge clk_sys) ddr_busy <= busypct != 0 && ($urandom % 100) < busypct;
    reg [7:0] read_beats = 0; reg read_pending = 0; reg [2:0] read_owner = 0;
    wire [2:0] owner = gq ? 3'd1 : dq ? 3'd4 : 3'd0;
    wire request = gq || dq || cq;
    wire write_request = owner == 4 ? 1'b1 : owner == 1 ? gw : cw;
    wire DDRAM_BUSY = ddr_busy;
    wire accepted = request && !holding && !read_pending && !DDRAM_BUSY;
    assign ca = accepted && owner == 0;
    assign ga = accepted && owner == 1;
    assign da = accepted && owner == 4;
    assign cv = DDRAM_DOUT_READY && read_pending && read_owner == 0;
    assign gv = DDRAM_DOUT_READY && read_pending && read_owner == 1;
    wire [28:0] DDRAM_ADDR = owner == 1 ? gad : owner == 4 ? dad : cad;
    wire [63:0] DDRAM_DIN = owner == 4 ? dwd : owner == 1 ? gwd : cwd;
    wire [7:0] DDRAM_BE = owner == 4 ? dbe : owner == 1 ? gbe : cbe;
    wire [7:0] DDRAM_BURSTCNT = (owner == 1 && !write_request) ? gburst :
                                (owner == 0 && !write_request) ? cburst : 8'd1;
    reg [28:0] rd_addr = 0; reg [7:0] rd_left = 0; integer rd_wait = 0; integer lane, logfd = 0;
    always @(posedge clk_sys) begin
        DDRAM_DOUT_READY <= 0;
        if (core_reset) read_pending <= 0;
        else begin
            if (DDRAM_DOUT_READY && read_pending) begin
                if (read_beats <= 8'd1) read_pending <= 0; else read_beats <= read_beats - 8'd1;
            end
            if (accepted && !write_request) begin
                read_pending <= 1; read_owner <= owner; read_beats <= DDRAM_BURSTCNT;
                rd_addr <= DDRAM_ADDR; rd_left <= DDRAM_BURSTCNT; rd_wait <= lat + (latrand != 0 ? $urandom % (latrand + 1) : 0);
            end
            if (accepted && write_request) begin
                if (DDRAM_ADDR >= 29'h06000000 && DDRAM_ADDR < 29'h06200000) begin
                    for (lane = 0; lane < 8; lane = lane + 1)
                        if (DDRAM_BE[lane]) ram[DDRAM_ADDR[20:0]][lane*8 +: 8] <= DDRAM_DIN[lane*8 +: 8];
                    if (owner != 0 && logfd != 0) $fdisplay(logfd, "D %h %h %h", DDRAM_ADDR, DDRAM_BE, DDRAM_DIN);
                end else $display("%0t: write outside RAM %h owner %0d", $time, DDRAM_ADDR, owner);
            end
            if (rd_left != 0) begin
                if (rd_wait != 0) rd_wait <= rd_wait - 1;
                else begin
                    DDRAM_DOUT <= rd_addr >= 29'h06400000 ? flash[rd_addr[17:0]] : ram[rd_addr[20:0]];
                    DDRAM_DOUT_READY <= 1; rd_addr <= rd_addr + 29'd1; rd_left <= rd_left - 8'd1;
                end
            end
        end
    end

    // ------------------------------------------- the stream for the shadow
    reg [31:0] last_pc = 0; reg [63:0] n_ret = 0; reg [31:0] n_irq = 0;
    always @(posedge clk2x) if (cpu.wb_valid) begin
        if (logfd != 0) begin
            if (cpu.wb_pc == 32'h80000180 && last_pc != 32'h8000017c && dbg_cause[6:2] == 5'd0)
                $fdisplay(logfd, "X %h %h", dbg_epc, dbg_cause);
            $fdisplay(logfd, "R %h %h %h", cpu.wb_pc, cpu.wb_rd, cpu.wb_data);
        end
        if (cpu.wb_pc == 32'h80000180 && last_pc != 32'h8000017c) n_irq <= n_irq + 1;
        last_pc <= cpu.wb_pc; n_ret <= n_ret + 1;
    end
    // +watchval=HEX: the first few times a register is written with that value, print the last
    // 4096 retired instructions (pc, register, value) - e.g. a string's address, to find the
    // code that chose it. +watchmax=N dumps (default 3).
    reg [31:0] watchval = 0; integer watchmax = 3, watchn = 0, wi;
    reg [69:0] wring [0:4095]; reg [11:0] wptr = 0;
    reg [31:0] watchaddr = 0; longint watchafter = 0;
    // +natives: every o-code native call (dispatcher 8006E6A8: a0 module, a1 function), with
    // a2/a3 and ra, from a shadow register file kept from the retire stream (sim diagnostic).
    reg [31:0] sreg [0:31]; reg natives = 0;
    always @(posedge clk2x) if (cpu.wb_valid) begin
        if (cpu.wb_rd[5] && cpu.wb_rd[4:0] != 0) sreg[cpu.wb_rd[4:0]] <= cpu.wb_data;
        if (natives && cpu.wb_pc[31:1] == 31'h4003_7354)
            $display("%0d us: NATIVE (%0d,0x%h) a2 %h a3 %h ra %h", cycles / 50, sreg[4], sreg[5][7:0], sreg[6], sreg[7], sreg[31]);
    end
    always @(posedge clk2x) if (cpu.wb_valid && (watchval != 0 || watchaddr != 0)) begin
        wring[wptr] <= {cpu.wb_rd, cpu.wb_pc, cpu.wb_data}; wptr <= wptr + 1;
        if (watchval != 0 && cpu.wb_rd[5] && cpu.wb_data == watchval && watchn < watchmax) begin
            watchn = watchn + 1;
            $display("WATCH %0d: %h written by %h after %0d instructions; the 4096 before it:", watchn, watchval, cpu.wb_pc, n_ret);
            for (wi = 1; wi <= 4096; wi = wi + 1)
                $display("  %h %s%0d %h", wring[(wptr - 4096 + wi - 1) & 12'hfff][63:32],
                         wring[(wptr - 4096 + wi - 1) & 12'hfff][69] ? "r" : "-",
                         wring[(wptr - 4096 + wi - 1) & 12'hfff][68:64], wring[(wptr - 4096 + wi - 1) & 12'hfff][31:0]);
            $display("  %h r%0d %h  <- here", cpu.wb_pc, cpu.wb_rd[4:0], cpu.wb_data);
            $fflush;
        end
    end
    always @(posedge clk_sys) if (iq && irdy && logfd != 0)
        $fdisplay(logfd, "M %0d %h %0d %h", iw, ia, iz, iw ? id : ir);
    // +watchaddr=HEX (physical): every cached load/store of that 32-bit word is printed; the
    // first +watchmax of them after +watchafter=N clk_sys cycles also print the 400 retired
    // instructions before it (the +watchval ring, which this enables).
    integer addrhits = 0;
    always @(posedge clk2x) if (watchaddr != 0 && (cpu.core.core.datacache_readena || cpu.core.core.datacache_writeena) &&
                                cpu.core.core.datacache_addr[28:2] == watchaddr[28:2] && cycles >= watchafter) begin
        addrhits = addrhits + 1;
        $display("%0d us: %s of %h (word %h) near pc %h, %0d instructions", cycles / 50,
                 cpu.core.core.datacache_writeena ? "STORE" : "LOAD", cpu.core.core.datacache_addr, watchaddr, cpu.wb_pc, n_ret);
        if (addrhits <= watchmax) begin
            for (wi = 3697; wi <= 4096; wi = wi + 1)
                $display("  %h %s%0d %h", wring[(wptr - 4096 + wi - 1) & 12'hfff][63:32],
                         wring[(wptr - 4096 + wi - 1) & 12'hfff][69] ? "r" : "-",
                         wring[(wptr - 4096 + wi - 1) & 12'hfff][68:64], wring[(wptr - 4096 + wi - 1) & 12'hfff][31:0]);
        end
        $fflush;
    end
    // +mlog=FILE: device register accesses only, with the time (no instruction stream)
    integer mlogfd = 0;
    always @(posedge clk_sys) if (iq && irdy && mlogfd != 0)
        $fdisplay(mlogfd, "%0d us %s %h %0d %h", cycles / 50, iw ? "W" : "R", ia, iz, iw ? id : ir);

    // ------------------------------------------- the video scan-out's descriptor check
    // rtl/pace_guide_video601.sv reads the OSD descriptor at osd_root from DDR every field and
    // latches C0/C1 on a malformed one. Not in this bench, so its check is done here, every
    // 2 ms (stricter than a field), on the DDR model: what any device would read.
    function automatic [31:0] be32(input [23:0] a);
        reg [63:0] q; integer o;
        q = ram[a[23:3]]; o = a[2:0];
        be32 = {q[o*8 +: 8], q[(o+1)*8 +: 8], q[(o+2)*8 +: 8], q[(o+3)*8 +: 8]};
    endfunction
    integer osd_bad = 0; reg [31:0] w8, w12, w16, w20; reg [23:0] d;
    reg [127:0] osd_prev = 0;
    always @(posedge clk_sys) if (!holding && cycles % 500 == 250 && osd_root[24]) begin
        d = osd_root[23:0];
        if ({be32(d + 8), be32(d + 12), be32(d + 16), be32(d + 20)} != osd_prev) begin
            $display("%0d us: OSD descriptor %h in DDR: +8 %h +12 %h +16 %h +20 %h (pc %h)", cycles / 50, d,
                     be32(d + 8), be32(d + 12), be32(d + 16), be32(d + 20), pc);
            osd_prev = {be32(d + 8), be32(d + 12), be32(d + 16), be32(d + 20)};
        end
    end
    always @(posedge clk_sys) if (!holding && cycles % 100000 == 50000 && osd_root[24] && osd_root[23:0] != 0) begin
        d = osd_root[23:0];
        w8 = be32(d + 8); w12 = be32(d + 12); w16 = be32(d + 16); w20 = be32(d + 20);
        if (d[2:0] != 0 || w8 != 32'h023f02cf || w12[2:0] != 0 || w16[26:25] != 3 || w16[2:0] != 0 || w20[2:0] != 0) begin
            osd_bad = osd_bad + 1;
            if (osd_bad <= 5)
                $display("%0d ms: OSD DESCRIPTOR INVALID in DDR at %h: +8 %h +12 %h +16 %h +20 %h (pc %h, %0d instructions)",
                         cycles / 50000, d, w8, w12, w16, w20, pc, n_ret);
        end
    end

    always @(posedge clk_sys) if (!holding && tsfd != 0) begin
        if (ts_valid && ts_ready) begin ts_valid <= 0; tswait <= tsgap; end
        else if (!ts_valid) begin
            if (tswait != 0) tswait <= tswait - 1;
            else begin
                tsc = $fgetc(tsfd);
                if (tsc < 0) begin void'($rewind(tsfd)); tsc = $fgetc(tsfd); end
                ts_byte <= tsc[7:0]; ts_valid <= 1;
            end
        end
    end

    // ------------------------------------------- run
    string ram_file, state_file, flash_file, log_file;
    longint cycles = 0, limit = 50000000, keyat = 0, status_every = 5000000;
    integer keyarg = 0, i, ki, nkeys = 0; longint keygap = 15000000; reg [7:0] keylist [0:15];
    string keystr;
    always @(posedge clk_sys) begin
        cycles <= cycles + 1;
        key_valid <= 0;
        if (keyat != 0 && cycles == keyat) begin key_valid <= 1; key_code <= keyarg[7:0]; end
        for (ki = 0; ki < nkeys; ki = ki + 1)
            if (keyat != 0 && cycles == keyat + ki * keygap) begin key_valid <= 1; key_code <= keylist[ki]; end
        if (cycles != 0 && cycles % status_every == 0)
            $display("%0d ms: pc %h retired %0d interrupts %0d cause %h epc %h gpu %0d keys %0d serial %0d errors %h unmapped %0d osd %h",
                     cycles / 50000, pc, n_ret, n_irq, dbg_cause, dbg_epc, gpu_count, key_frames, serial_frames,
                     cpu_errors, cpu_unmapped, osd_root);
        if (cycles != 0 && cycles % status_every == 0) $fflush;
        if (cpu_errors != 0 || model_halt != 0 || gpu_error != 0) begin
            $display("STOP: cpu errors %h model halt %h gpu error %h at pc %h after %0d instructions",
                     cpu_errors, model_halt, gpu_error, pc, n_ret);
            if (logfd != 0) $fclose(logfd);
            $finish;
        end
        if (cycles >= limit) begin
            $display("done: %0d clk_sys cycles, %0d instructions, %0d interrupts, pc %h", cycles, n_ret, n_irq, pc);
            if (logfd != 0) $fclose(logfd);
            $finish;
        end
    end
    initial begin
        if (!$value$plusargs("ram=%s", ram_file)) ram_file = "/tmp/ram_guide.hex";
        if (!$value$plusargs("state=%s", state_file)) state_file = "/tmp/state_guide.hex";
        if (!$value$plusargs("flash=%s", flash_file)) flash_file = "sim/fullflash_ddr.hex";
        if ($value$plusargs("log=%s", log_file)) logfd = $fopen(log_file, "w");
        if ($value$plusargs("cycles=%d", limit)) ;
        if ($value$plusargs("key=%h", keyarg)) ;
        if ($value$plusargs("keyat=%d", keyat)) ;
        if ($value$plusargs("keygap=%d", keygap)) ;
        if ($value$plusargs("mlog=%s", keystr)) mlogfd = $fopen(keystr, "w");
        if ($value$plusargs("watchval=%h", watchval)) ;
        if ($value$plusargs("watchmax=%d", watchmax)) ;
        if ($value$plusargs("watchaddr=%h", watchaddr)) ;
        if ($value$plusargs("watchafter=%d", watchafter)) ;
        natives = $test$plusargs("natives");
        if ($value$plusargs("keys=%s", keystr)) begin
            for (i = 0; i + 1 < keystr.len() && nkeys < 16; i = i + 3) begin
                keylist[nkeys] = keystr.substr(i, i + 1).atohex(); nkeys = nkeys + 1;
            end
        end
        if ($value$plusargs("status=%d", status_every)) ;
        if ($value$plusargs("lat=%d", lat)) ;
        if ($value$plusargs("ts=%s", log_file)) tsfd = $fopen(log_file, "rb");
        if ($value$plusargs("tsgap=%d", tsgap)) ;
        if ($value$plusargs("log=%s", log_file)) ;
        if ($value$plusargs("latrand=%d", latrand)) ;
        if ($value$plusargs("busy=%d", busypct)) ;
        if ($value$plusargs("seed=%d", i)) void'($urandom(i));
        $readmemh(ram_file, ram); $readmemh(flash_file, flash); $readmemh(state_file, state_words);
        repeat (8) @(negedge clk_sys); core_reset = 0;
        for (i = 0; i < 68; i = i + 1) begin
            state_write = 1; state_index = i[6:0]; state_data = state_words[i]; @(negedge clk_sys);
        end
        state_write = 0; loaded_state = 1;
        repeat (8) @(negedge clk_sys); holding = 0;
    end
endmodule
