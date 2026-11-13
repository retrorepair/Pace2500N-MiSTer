// SPDX-License-Identifier: GPL-3.0-only
// The Pace 2500N's NEC VR4110-class CPU: the pipelined, cached MIPS from rtl/r4k (KI MiSTer
// core's CPU, see rtl/r4k/UPSTREAM.md) with MIPS16, VR4110 caches and checkpoint start, joined
// to the Live core's memory system.
//
// Clocks: clk2x is the CPU core, clk1x its memory side (2:1, phase-aligned outputs of one PLL,
// as the KI CPU requires). clk_sys is the system clock (DDR3 arbiter, device registers); it is
// asynchronous to clk1x, so each CPU memory transaction crosses by a toggle handshake: the
// request payload is held still in the clk1x domain until the clk_sys side answers, and the
// answer is held still in the clk_sys domain until the next request.
//
// Physical map (as pace_firmware_cpu): RAM 0x00000000-0x00FFFFFF -> DDR 0x30000000; flash
// 0x1FC00000-0x1FDFFFFF -> DDR 0x32000000, also read at 0x1F800000-0x1FBFFFFF; device registers
// 0x10000000-0x100FFFFF, 0x12000000-0x120FFFFF, 0x14080000-0x1408FFFF and 0x14180000 (byte
// writes) on the existing io_* bus as KSEG1 addresses with the access size the firmware used.
// Anything else reads 0 and drops writes, counted in `unmapped`.
module pace_r4k #(
    parameter integer COUNT_NUM = 27,   // Count = 20.25 MHz at a 75 MHz clk2x
    parameter integer COUNT_DEN = 100
)(
    input  wire        clk_sys, clk1x, clk2x,
    input  wire        reset_sys,       // core reset (clk_sys)
    input  wire        hold_sys,        // downloads in progress / images not loaded (clk_sys)
    input  wire        ckpt_loaded,     // STATE.bin has been loaded (clk_sys)
    input  wire        state_wr,        // STATE.bin download word (clk_sys)
    input  wire  [6:0] state_index,
    input  wire [31:0] state_data,
    input  wire        io_irq,          // EMMA interrupt controller -> IP2 (clk_sys)
    // DDR3 arbiter port (clk_sys), 64-bit word addresses
    output reg         ddr_req = 1'b0,
    output reg         ddr_we = 1'b0,
    output reg  [28:0] ddr_addr = 29'd0,
    output reg  [63:0] ddr_wdata = 64'd0,
    output reg   [7:0] ddr_be = 8'd0,
    output reg   [7:0] ddr_burst = 8'd1,
    input  wire        ddr_accept, ddr_rvalid,
    input  wire [63:0] ddr_rdata,
    // device registers (clk_sys), as pace_firmware_cpu's io_*
    output reg         io_req = 1'b0,
    output reg         io_we = 1'b0,
    output reg  [31:0] io_addr = 32'd0,
    output reg  [31:0] io_wdata = 32'd0,
    output reg   [1:0] io_size = 2'd2,
    input  wire [31:0] io_rdata,
    input  wire        io_ready,
    // telemetry
    output wire [31:0] pc,
    output wire [31:0] retired,
    // diagnostics (clk2x counters, sampled by the telemetry UART without a CDC: approximate)
    output reg  [31:0] dbg_fetch_stall = 32'd0,   // cycles stage 1/2 waited on the I-cache
    output reg  [31:0] dbg_cached_stall = 32'd0,  // cycles stage 4 waited on a cached access
    output reg  [31:0] dbg_mem_stall = 32'd0,     // cycles stage 4 waited on memory (all)
    output reg  [31:0] dbg_exceptions = 32'd0,    // exception entries (EXL rising)
    output wire [31:0] dbg_cause,                 // live Cause/Status (cpu_cop0 debug_cause)
    output wire [31:0] dbg_epc,                   // live EPC
    output wire [31:0] dbg_badvaddr,              // live BadVAddr
    // retire trace: the last 128 retired instructions (pc, register written, value), frozen
    // when the firmware's TLB-refill panic path (80000048) retires; read a page of 5 per PROF frame
    input  wire        trace_next,                // clk_sys pulse: a PROF frame was sent
    input  wire        trace_trigger,             // clk_sys pulse: freeze the trace now
    output wire        trace_frozen,              // clk_sys: the trace is frozen (send pages fast)
    output reg [511:0] trace_page_data = 512'd0,
    output wire  [5:0] errors,
    output reg  [31:0] unmapped = 32'd0
);
    // ---------------------------------------------------------------- checkpoint and resets
    reg [31:0] state_regs [0:67];
    always @(posedge clk_sys) if (state_wr && state_index < 7'd68) state_regs[state_index] <= state_data;

    reg [2:0] hold2_s = 3'b111, loaded2_s = 3'b000;
    always @(posedge clk2x) begin
        hold2_s   <= {hold2_s[1:0], hold_sys | reset_sys};
        loaded2_s <= {loaded2_s[1:0], ckpt_loaded};
    end
    wire hold2 = hold2_s[2];
    // While held: reset. Then copy STATE into the CPU (still in reset), then run.
    reg        rst2x = 1'b1, copying = 1'b0, copied = 1'b0;
    reg  [6:0] copy_i = 7'd0;
    reg        ckpt_wr = 1'b0;
    reg  [6:0] ckpt_index = 7'd0;
    reg [31:0] ckpt_data = 32'd0;
    always @(posedge clk2x) begin
        ckpt_wr <= 1'b0;
        if (hold2) begin
            rst2x <= 1'b1; copying <= 1'b0; copied <= 1'b0; copy_i <= 7'd0;
        end else if (!copied) begin
            copying    <= 1'b1;
            ckpt_wr    <= 1'b1;
            ckpt_index <= copy_i;
            ckpt_data  <= state_regs[copy_i];   // static: the download has finished
            if (copy_i == 7'd67) begin copied <= 1'b1; copying <= 1'b0; end
            else copy_i <= copy_i + 7'd1;
        end else begin
            rst2x <= 1'b0;
        end
    end
    reg [1:0] rst1x_s = 2'b11;
    always @(posedge clk1x) rst1x_s <= {rst1x_s[0], rst2x};
    wire rst1x = rst1x_s[1];
    reg [1:0] irq2_s = 2'b00;
    always @(posedge clk2x) irq2_s <= {irq2_s[0], io_irq};

    // ---------------------------------------------------------------- the CPU
    wire        mem_request, mem_rnw, mem_req64, mem_line_write;
    wire [31:0] mem_address;
    wire  [2:0] mem_size;
    wire  [7:0] mem_writeMask;
    wire [63:0] mem_dataWrite;
    wire [255:0] mem_line_data;
    wire [31:0] mem_line_bytes;
    reg  [63:0] mem_dataRead = 64'd0;
    reg         mem_done = 1'b0, grant = 1'b0, dout_ready = 1'b0;
    reg  [63:0] dout = 64'd0;
    wire [11:0] perf;

    pace_r4k_core #(.COUNT_NUM(COUNT_NUM), .COUNT_DEN(COUNT_DEN)) core (
        .clk1x(clk1x), .clk2x(clk2x), .reset_1x(rst1x), .reset_2x(rst2x), .irq(irq2_s[1]),
        .mem_request(mem_request), .mem_rnw(mem_rnw), .mem_address(mem_address), .mem_req64(mem_req64),
        .mem_size(mem_size), .mem_writeMask(mem_writeMask), .mem_dataWrite(mem_dataWrite),
        .mem_line_write(mem_line_write), .mem_line_data(mem_line_data), .mem_line_bytes(mem_line_bytes),
        .mem_dataRead(mem_dataRead), .mem_done(mem_done), .grant(grant), .dout(dout), .dout_ready(dout_ready),
        .ckpt_valid(loaded2_s[2]), .ckpt_wr(ckpt_wr), .ckpt_index(ckpt_index), .ckpt_data(ckpt_data),
        .errors(errors), .fetch_pc(pc), .retired(retired), .perf(perf), .cause(dbg_cause),
        .epc(dbg_epc), .badvaddr(dbg_badvaddr),
        .wb_valid(wb_valid), .wb_pc(wb_pc), .wb_rd(wb_rd), .wb_data(wb_data));
    wire        wb_valid;
    wire [31:0] wb_pc, wb_data;
    wire  [5:0] wb_rd;
    reg  [69:0] ring [0:1023];
    reg   [9:0] wptr = 10'd0;
    reg         frozen = 1'b0;
    reg         trig_req = 1'b0;           // clk_sys: trace_trigger seen
    reg   [1:0] trig_s = 2'b00;
    always @(posedge clk_sys) if (reset_sys) trig_req <= 1'b0; else if (trace_trigger) trig_req <= 1'b1;
    always @(posedge clk2x) begin
        trig_s <= {trig_s[0], trig_req};
        if (rst2x) begin
            frozen <= 1'b0;
        end else if (!frozen) begin
            if (wb_valid) begin
                ring[wptr] <= {wb_rd, wb_pc, wb_data};
                wptr <= wptr + 10'd1;
            end
            if ((wb_valid && wb_pc == 32'h80000048) || trig_s[1]) frozen <= 1'b1;
        end
    end
    reg  [1:0] frozen_s = 2'b00;
    reg [159:0] bring [0:63];   // bus transaction trace (written on the clk_sys side below)
    reg   [5:0] bptr = 6'd0;
    reg  [7:0] page = 8'd0;
    reg  [2:0] slot = 3'd7;
    reg  [9:0] raddr = 10'd0;
    reg  [5:0] baddr = 6'd0;
    reg  [69:0] rq;
    reg [159:0] bq;
    reg  [2:0] rslot = 3'd7, rslot2 = 3'd7;
    wire       bpage = page >= 8'd205;
    wire [7:0] bp = page - 8'd205;
    assign trace_frozen = frozen_s[1];
    always @(posedge clk_sys) begin
        frozen_s <= {frozen_s[0], frozen};
        rq <= ring[raddr];
        bq <= bring[baddr];
        rslot <= slot; rslot2 <= rslot;
        if (trace_next) begin page <= page == 8'd226 ? 8'd0 : page + 8'd1; slot <= 3'd0; end
        else if (slot != 3'd7) slot <= slot == 3'd4 ? 3'd7 : slot + 3'd1;
        // pages 0-204: retired instruction k = 5*page + slot, newest first (k = 0 froze it)
        raddr <= wptr - 10'd1 - ({2'd0, page} * 10'd5 + {7'd0, slot});
        // pages 205-226: bus transaction k = 3*(page-205) + slot, newest first
        baddr <= bptr - 6'd1 - (bp[5:0] * 6'd3 + {3'd0, slot});
        if (rslot2 != 3'd7 && !bpage) begin
            trace_page_data[(1 + 3*rslot2)*32 +: 32] <= rq[63:32];            // pc
            trace_page_data[(2 + 3*rslot2)*32 +: 32] <= {26'd0, rq[69:64]};   // write enable, target
            trace_page_data[(3 + 3*rslot2)*32 +: 32] <= rq[31:0];             // value
        end
        if (rslot2 < 3'd3 && bpage) begin                                     // addr, flags, 3 data words
            trace_page_data[(1 + 5*rslot2)*32 +: 32] <= bq[159:128];
            trace_page_data[(2 + 5*rslot2)*32 +: 32] <= bq[127:96];
            trace_page_data[(3 + 5*rslot2)*32 +: 32] <= bq[95:64];
            trace_page_data[(4 + 5*rslot2)*32 +: 32] <= bq[63:32];
            trace_page_data[(5 + 5*rslot2)*32 +: 32] <= bq[31:0];
        end
        trace_page_data[31:0] <= {8'hA5, frozen_s[1], 5'd0, wptr, page};
    end
    reg exl_q = 1'b0;
    always @(posedge clk2x) begin
        exl_q <= dbg_cause[16];
        if (perf[8]) dbg_fetch_stall <= dbg_fetch_stall + 32'd1;
        if (perf[5]) dbg_cached_stall <= dbg_cached_stall + 32'd1;
        if (perf[2]) dbg_mem_stall <= dbg_mem_stall + 32'd1;
        if (dbg_cause[16] && !exl_q) dbg_exceptions <= dbg_exceptions + 32'd1;
    end

    // ---------------------------------------------------------------- clk1x side
    // Held payload (read by clk_sys after req_tog crosses).
    reg         p_rnw = 1'b1, p_req64 = 1'b0, p_line = 1'b0, p_lw = 1'b0;
    reg  [31:0] p_addr = 32'd0;
    reg   [7:0] p_mask = 8'd0;
    reg  [63:0] p_wdata = 64'd0;
    reg [255:0] p_ldata = 256'd0;
    reg  [31:0] p_lbytes = 32'd0;
    reg         req_tog = 1'b0;
    reg   [2:0] ack1_s = 3'b000;
    // Answer (written by clk_sys before ack_tog flips).
    reg  [63:0] r_data = 64'd0;
    reg  [63:0] r_line [0:3];
    reg         ack_tog = 1'b0;

    localparam C_IDLE = 3'd0, C_WAIT = 3'd1, C_GRANT = 3'd2, C_BEATS = 3'd3, C_DONE = 3'd4;
    reg [2:0] cstate = C_IDLE;
    reg [1:0] beat = 2'd0;
    always @(posedge clk1x) begin
        ack1_s <= {ack1_s[1:0], ack_tog};
        mem_done <= 1'b0; grant <= 1'b0; dout_ready <= 1'b0;
        if (rst1x) begin
            cstate <= C_IDLE;
        end else case (cstate)
            C_IDLE: if (mem_request) begin
                p_rnw <= mem_rnw; p_addr <= mem_address; p_req64 <= mem_req64;
                p_line <= mem_size == 3'b100; p_mask <= mem_writeMask; p_wdata <= mem_dataWrite;
                p_lw <= mem_line_write; p_ldata <= mem_line_data; p_lbytes <= mem_line_bytes;
                req_tog <= ~req_tog;
                cstate <= C_WAIT;
            end
            C_WAIT: if (ack1_s[2] == req_tog) begin
                if (p_rnw) begin grant <= 1'b1; cstate <= p_line ? C_BEATS : C_DONE; beat <= 2'd0; end
                else begin mem_done <= 1'b1; cstate <= C_IDLE; end
            end
            C_BEATS: begin   // the 32-byte line, in address order; done beside the last
                dout <= r_line[beat]; dout_ready <= 1'b1;
                if (beat == 2'd3) begin mem_done <= 1'b1; cstate <= C_IDLE; end
                beat <= beat + 2'd1;
            end
            C_DONE: begin mem_dataRead <= r_data; mem_done <= 1'b1; cstate <= C_IDLE; end
            default: cstate <= C_IDLE;
        endcase
    end

    // ---------------------------------------------------------------- clk_sys side
    reg [2:0] req_s = 3'b000;
    always @(posedge clk_sys) req_s <= {req_s[1:0], req_tog};
    wire pending = req_s[2] != ack_tog;

    wire [28:0] phys = p_addr[28:0];
    wire is_ram   = phys[28:24] == 5'd0;
    wire is_flash = phys[28:21] == 8'hFE;                              // 1FC00000-1FDFFFFF
    wire is_fmirr = (phys & 29'h1FC00000) == 29'h1F800000;             // 1F800000-1FBFFFFF (reads)
    wire is_io    = phys[28:20] == 9'h100 || phys[28:20] == 9'h120 || phys[28:16] == 13'h1408 ||
                    (phys == 29'h14180000 && !p_rnw);
    wire [28:0] ddr_word = is_ram ? 29'h06000000 + {5'd0, phys[23:3]} :
                           is_flash ? 29'h06400000 + {8'd0, phys[20:3]} :
                                      29'h06400000 + {7'd0, phys[21:3]};
    // Device access size and byte offset from the byte mask (bit k = byte k of the word).
    reg [1:0] io_sz, io_off;
    always @* case (p_mask[3:0])
        4'b0001: begin io_sz = 2'd0; io_off = 2'd0; end
        4'b0010: begin io_sz = 2'd0; io_off = 2'd1; end
        4'b0100: begin io_sz = 2'd0; io_off = 2'd2; end
        4'b1000: begin io_sz = 2'd0; io_off = 2'd3; end
        4'b0011: begin io_sz = 2'd1; io_off = 2'd0; end
        4'b1100: begin io_sz = 2'd1; io_off = 2'd2; end
        default: begin io_sz = 2'd2; io_off = 2'd0; end
    endcase
    wire [31:0] w = p_wdata[31:0];   // a 32-bit store's word, bus (address) order
    wire [31:0] io_value = io_sz == 2'd0 ? {24'd0, w[io_off*8 +: 8]} :
                           io_sz == 2'd1 ? {16'd0, w[io_off*8 +: 8], w[io_off*8+8 +: 8]} :
                                           {w[7:0], w[15:8], w[23:16], w[31:24]};
    function automatic [31:0] io_lanes(input [31:0] v, input [1:0] sz, input [1:0] off);
        reg [31:0] b;
        begin
            b = 32'd0;
            if (sz == 2'd0) b[off*8 +: 8] = v[7:0];
            else if (sz == 2'd1) begin b[off*8 +: 8] = v[15:8]; b[off*8+8 +: 8] = v[7:0]; end
            else b = {v[7:0], v[15:8], v[23:16], v[31:24]};
            io_lanes = b;
        end
    endfunction

    // bus transaction trace (bring-up): one entry per completed CPU transaction
    reg         ack_q = 1'b0;
    always @(posedge clk_sys) begin
        ack_q <= ack_tog;
        if (ack_tog != ack_q && !frozen_s[1]) begin
            bring[bptr] <= {p_addr,
                            {20'd0, p_mask, p_rnw, p_line, p_lw, is_io},
                            p_line ? r_line[0][31:0] : p_rnw ? r_data[31:0] : p_lw ? p_ldata[31:0]   : p_wdata[31:0],
                            p_line ? r_line[1][31:0] : p_rnw ? r_data[63:32] : p_lw ? p_ldata[95:64] : p_wdata[63:32],
                            p_line ? r_line[2][31:0] : p_lw ? p_ldata[159:128] : 32'd0};
            bptr <= bptr + 6'd1;
        end
    end

    localparam S_IDLE = 3'd0, S_DDRRD = 3'd1, S_DDRBEAT = 3'd2, S_DDRWR = 3'd3, S_IO = 3'd4;
    reg [2:0] sstate = S_IDLE;
    reg [1:0] q = 2'd0;
    reg [2:0] got = 3'd0;
    always @(posedge clk_sys) begin
        if (reset_sys) begin
            sstate <= S_IDLE; ddr_req <= 1'b0; io_req <= 1'b0;
        end else case (sstate)
            S_IDLE: if (pending) begin
                if (is_io) begin
                    io_req <= 1'b1; io_we <= !p_rnw; io_size <= io_sz;
                    io_addr <= {3'b101, phys[28:2], io_off}; io_wdata <= io_value;
                    sstate <= S_IO;
                end else if (p_rnw && (is_ram || is_flash || is_fmirr)) begin
                    ddr_req <= 1'b1; ddr_we <= 1'b0;
                    ddr_addr <= p_line ? {ddr_word[28:2], 2'b00} : ddr_word;
                    ddr_burst <= p_line ? 8'd4 : 8'd1;
                    got <= 3'd0;
                    sstate <= S_DDRRD;
                end else if (!p_rnw && is_ram) begin
                    q <= 2'd0;
                    sstate <= S_DDRWR;
                end else begin
                    // outside the map: reads 0, writes dropped (flash is not written by the CPU)
                    r_data <= 64'd0; r_line[0] <= 64'd0; r_line[1] <= 64'd0; r_line[2] <= 64'd0; r_line[3] <= 64'd0;
                    unmapped <= unmapped + 32'd1;
                    ack_tog <= req_s[2];
                end
            end
            S_DDRRD: if (ddr_accept) begin ddr_req <= 1'b0; sstate <= S_DDRBEAT; end
            S_DDRBEAT: if (ddr_rvalid) begin
                if (p_line) begin
                    r_line[got[1:0]] <= ddr_rdata;
                    if (got == 3'd3) begin ack_tog <= req_s[2]; sstate <= S_IDLE; end
                    got <= got + 3'd1;
                end else begin
                    r_data <= p_req64 ? ddr_rdata : phys[2] ? {32'd0, ddr_rdata[63:32]} : {32'd0, ddr_rdata[31:0]};
                    ack_tog <= req_s[2]; sstate <= S_IDLE;
                end
            end
            S_DDRWR: begin
                // a whole line (its present qwords) or one doubleword/word
                if (!ddr_req) begin
                    if (p_lw) begin
                        if (p_mask[q]) begin
                            ddr_req <= 1'b1; ddr_we <= 1'b1; ddr_burst <= 8'd1;
                            ddr_addr <= {ddr_word[28:2], q};
                            ddr_wdata <= p_ldata[q*64 +: 64]; ddr_be <= p_lbytes[q*8 +: 8];
                        end else if (q == 2'd3) begin
                            ack_tog <= req_s[2]; sstate <= S_IDLE;
                        end else q <= q + 2'd1;
                    end else begin
                        ddr_req <= 1'b1; ddr_we <= 1'b1; ddr_burst <= 8'd1; ddr_addr <= ddr_word;
                        ddr_wdata <= p_req64 ? p_wdata : phys[2] ? {p_wdata[31:0], 32'd0} : {32'd0, p_wdata[31:0]};
                        ddr_be    <= p_req64 ? p_mask  : phys[2] ? {p_mask[3:0], 4'd0} : {4'd0, p_mask[3:0]};
                        q <= 2'd3;
                    end
                end else if (ddr_accept) begin
                    ddr_req <= 1'b0;
                    if (q == 2'd3) begin ack_tog <= req_s[2]; sstate <= S_IDLE; end
                    else q <= q + 2'd1;
                end
            end
            S_IO: if (io_ready) begin
                io_req <= 1'b0;
                r_data <= {32'd0, io_lanes(io_rdata, io_size, io_addr[1:0])};
                ack_tog <= req_s[2]; sstate <= S_IDLE;
            end
            default: sstate <= S_IDLE;
        endcase
    end
endmodule
