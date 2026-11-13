// Shadow check for the system simulation (Verilator): the old CPU (rtl/pace_firmware_cpu.sv,
// the one v0.6.3 runs) re-executes, instruction by instruction, what the new CPU did in
// sim/vl/tb_sys.sv, and the first difference is reported.
//
// It starts from the same checkpoint with its own copy of RAM and reads tb_sys's stream
// (+log=FILE or a named pipe):
//   R pc rd data   compared with each instruction the old CPU retires (pc, MIPS16 mode,
//                  register written and value). A MIPS16 EXTEND / JAL first half is its own
//                  R line in the new CPU (no register), and is folded here.
//   X epc cause    the old CPU is made to take an interrupt at this boundary (its own
//                  interrupt logic is off); its EPC and delay-slot flag must match.
//   M ...          device reads return the value the new CPU read (address and size must
//                  match); device writes are compared in order.
//   D ...          RAM writes by devices are applied to this copy of RAM.
// CP0 Count, Cause and Random reads take the new CPU's value (they depend on time).
// The old CPU copy with those hooks is made by sim/vl/vl_patch.py.
`timescale 1ps/1ps
module tb_shadow;
    reg clk = 0; always #1 clk = ~clk;
    reg reset = 1, hold = 1;
    reg restore_wr = 0; reg [6:0] restore_index = 0; reg [31:0] restore_data = 0;
    reg boot_load = 0; reg [16:0] boot_load_addr = 0; reg [15:0] boot_load_data = 0;
    reg [31:0] state_words [0:68];
    reg [63:0] ram [0:2097151];
    reg [63:0] flash [0:262143];

    wire mq, mw; wire [28:0] mad; wire [63:0] mwd; wire [7:0] mbe;
    reg mv = 0; reg [63:0] mrd = 0;
    wire iq, iw; wire [31:0] ia, id, pc, ret; wire [1:0] iz; wire [7:0] halt; wire m16;
    reg [31:0] io_rdata = 0;
    reg rp_take = 0; reg [31:0] rp_cause = 0, rp_value = 0;

    pace_firmware_cpu #(.EXTERNAL_MMIO(1), .CHECKPOINT_PORT(1), .RETIRE_TIMING(1), .BOOT_LOAD(1)) cpu (
        .clk(clk), .reset(reset), .full_flash_loaded(1'b1), .mmio_policy(2'd1),
        .boot_load(boot_load), .boot_load_addr(boot_load_addr), .boot_load_data(boot_load_data),
        .checkpoint_hold(hold), .checkpoint_wr(restore_wr), .checkpoint_index(restore_index), .checkpoint_data(restore_data),
        .io_req(iq), .io_we(iw), .io_addr(ia), .io_wdata(id), .io_size(iz), .io_rdata(io_rdata), .io_ready(iq), .io_irq(1'b0),
        .rp_take(rp_take), .rp_cause(rp_cause), .rp_patch(1'b1), .rp_value(rp_value),
        .mem_req(mq), .mem_we(mw), .mem_addr(mad), .mem_wdata(mwd), .mem_be(mbe),
        .mem_accept(mq && !hold), .mem_rvalid(mv), .mem_rdata(mrd),
        .pc(pc), .instruction(), .retired(ret), .ram_writes(), .last_ram_address(), .last_mmio_address(),
        .last_mmio_value(), .last_mmio_read(), .mmio_writes(), .guessed_reads(), .halt_code(halt),
        .mips16(m16), .reached_mips16());

    // ------------------------------------------- the stream
    typedef struct { bit x; bit [31:0] a; bit [31:0] b; bit [31:0] c; } rec_t;   // R: pc rd data; X: epc cause
    typedef struct { bit [31:0] addr; bit [1:0] size; bit [31:0] value; } io_t;
    rec_t rq [$]; io_t rdq [$], wrq [$], mywr [$];
    integer fd = 0; bit eof = 0; longint lines = 0;
    string line, log_file, ram_file, state_file, flash_file;
    task automatic fill();
        rec_t r; io_t m; bit [31:0] a, b, c; integer w, sz, lane; bit [63:0] d; bit [7:0] be; bit [28:0] da;
        while (!eof && rq.size() < 8) begin
            if ($fgets(line, fd) == 0) begin eof = 1; break; end
            lines++;
            case (line[0])
                "R": if ($sscanf(line, "R %h %h %h", a, b, c) == 3) begin r.x = 0; r.a = a; r.b = b; r.c = c; rq.push_back(r); end
                "X": if ($sscanf(line, "X %h %h", a, b) == 2) begin r.x = 1; r.a = a; r.b = b; r.c = 0; rq.push_back(r); end
                "M": if ($sscanf(line, "M %d %h %d %h", w, a, sz, c) == 4) begin
                         m.addr = a; m.size = sz[1:0]; m.value = c;
                         if (w != 0) wrq.push_back(m); else rdq.push_back(m);
                     end
                "D": if ($sscanf(line, "D %h %h %h", da, be, d) == 3) begin
                         for (lane = 0; lane < 8; lane++) if (be[lane]) ram[da[20:0]][lane*8 +: 8] = d[lane*8 +: 8];
                     end
                default: ;
            endcase
        end
    endtask

    function automatic bit [15:0] code16(input bit [31:0] a);   // halfword at a KSEG0/1 address
        bit [63:0] w; bit [7:0] hi, lo; bit [28:0] p;
        p = a[28:0];
        w = p >= 29'h1fc00000 ? flash[p[20:3]] : ram[p[23:3]];
        hi = w[{p[2:1], 1'b0} * 8 +: 8]; lo = w[{p[2:1], 1'b1} * 8 +: 8];
        return {hi, lo};
    endfunction
    function automatic bit two_halves(input bit [31:0] a);       // MIPS16 EXTEND or JAL/JALX
        bit [15:0] h = code16(a);
        return h[15:11] == 5'b11110 || h[15:11] == 5'b00011;
    endfunction

    // ------------------------------------------- checking
    longint checked = 0, taken = 0, limit = 0, report_every = 2000000;
    reg [31:0] prev_pc = 0, prev_ret = 0; reg prev_m16 = 0; reg started = 0;
    rec_t hist [0:31]; integer hp = 0, hi_;
    task automatic fail(input string why);
        $display("DIVERGENCE after %0d instructions (%0d interrupts): %s", checked, taken, why);
        $display("  old CPU: pc %h mode %0d wrote %s r%0d = %h; next pc %h", prev_pc, prev_m16,
                 cpu.gw_en ? "" : "(nothing)", cpu.gw_idx, cpu.gw_val, pc);
        $display("  last records from the new CPU (oldest first):");
        for (hi_ = 0; hi_ < 32; hi_++)
            if (hist[(hp + hi_) % 32].x) $display("    X epc %h cause %h", hist[(hp + hi_) % 32].a, hist[(hp + hi_) % 32].b);
            else $display("    R %h %s r%0d = %h", hist[(hp + hi_) % 32].a, hist[(hp + hi_) % 32].b[5] ? "write" : "     ",
                          hist[(hp + hi_) % 32].b[4:0], hist[(hp + hi_) % 32].c);
        $display("  queued next: %0d records", rq.size());
        for (hi_ = 0; hi_ < 6 && hi_ < rq.size(); hi_++)
            $display("    %s %h %h %h", rq[hi_].x ? "X" : "R", rq[hi_].a, rq[hi_].b, rq[hi_].c);
        $finish;
    endtask
    function automatic rec_t pop();
        rec_t r = rq.pop_front();
        hist[hp] = r; hp = (hp + 1) % 32;
        return r;
    endfunction

    rec_t r; io_t m, n; integer lane;
    always @(posedge clk) begin
        mv <= 0;
        if (!reset && !hold) begin
            // memory, one cycle
            if (mq) begin
                if (mad >= 29'h06400000 && mad < 29'h06440000) begin
                    if (!mw) begin mrd <= flash[mad[17:0]]; mv <= 1; end
                end else if (mad >= 29'h06000000 && mad < 29'h06200000) begin
                    if (mw) begin for (lane = 0; lane < 8; lane++) if (mbe[lane]) ram[mad[20:0]][lane*8 +: 8] <= mwd[lane*8 +: 8]; end
                    else begin mrd <= ram[mad[20:0]]; mv <= 1; end
                end else fail($sformatf("old CPU accesses memory outside the map: %h", mad));
            end
            // device registers
            if (iq) begin
                if (iw) begin m.addr = ia; m.size = iz; m.value = id; mywr.push_back(m); end
                else begin
                    if (rdq.size() == 0) fail($sformatf("old CPU reads device register %h, the new CPU read none here", ia));
                    else begin
                        m = rdq.pop_front();
                        if (m.addr != ia || m.size != iz)
                            fail($sformatf("device read: old CPU %h size %0d, new CPU %h size %0d", ia, iz, m.addr, m.size));
                    end
                end
            end
            while (mywr.size() != 0 && wrq.size() != 0) begin
                m = mywr.pop_front(); n = wrq.pop_front();
                if (m.addr != n.addr || m.size != n.size || m.value != n.value)
                    fail($sformatf("device write: old CPU %h size %0d = %h, new CPU %h size %0d = %h",
                                   m.addr, m.size, m.value, n.addr, n.size, n.value));
            end
            // an interrupt taken at this boundary
            if (rp_take && cpu.state == 5'd0) begin
                r = pop(); taken++;
                if (r.a != (cpu.delay_slot ? (cpu.branch_pc | {31'd0, cpu.branch_mode16}) : (pc | {31'd0, m16})) ||
                    r.b[31] != cpu.delay_slot)
                    fail($sformatf("interrupt: new CPU EPC %h BD %0d, old CPU would save %h BD %0d (Status %h)", r.a, r.b[31],
                                   cpu.delay_slot ? (cpu.branch_pc | {31'd0, cpu.branch_mode16}) : (pc | {31'd0, m16}),
                                   cpu.delay_slot, cpu.cp0[12]));
            end
            // an instruction retired on the previous edge
            if (ret != prev_ret) begin
                fill();
                if (rq.size() == 0) begin
                    $display("stream ended: %0d instructions and %0d interrupts identical", checked, taken); $finish;
                end
                r = pop();
                if (!started) begin
                    // the stream may open with records from before the checkpoint's first instruction
                    while (!r.x && r.a[31:1] != prev_pc[31:1] && rq.size() != 0 && lines < 64) r = pop();
                    started = 1;
                end
                if (!r.x && prev_m16 && two_halves(prev_pc) && r.a[31:1] == prev_pc[31:1] && !r.b[5] && rq.size() != 0 && !rq[0].x)
                    r = pop();   // the prefix half
                if (r.x) fail("the new CPU took an interrupt where the old CPU was not at an instruction boundary");
                else if (r.a[31:1] != prev_pc[31:1] || r.a[0] != prev_m16)
                    fail($sformatf("flow: new CPU retired %h, old CPU %h mode %0d", r.a, prev_pc, prev_m16));
                else if ((r.b[5] && r.b[4:0] != 0) != cpu.gw_en ||
                         (cpu.gw_en && (r.b[4:0] != cpu.gw_idx || r.c != cpu.gw_val)))
                    fail($sformatf("result at %h: new CPU %s r%0d = %h, old CPU %s r%0d = %h", r.a,
                                   r.b[5] ? "wrote" : "wrote nothing", r.b[4:0], r.c,
                                   cpu.gw_en ? "wrote" : "wrote nothing", cpu.gw_idx, cpu.gw_val));
                checked++;
                if (checked % report_every == 0) begin $display("%0d instructions, %0d interrupts identical", checked, taken); $fflush; end
                if (limit != 0 && checked >= limit) begin
                    $display("limit: %0d instructions and %0d interrupts identical", checked, taken); $finish;
                end
            end
            // what the next instruction needs: an interrupt first, or its Count/Cause value.
            // (A prefix half retired by the new CPU before it took the interrupt is dropped.)
            fill();
            if (rq.size() >= 2 && !rq[0].x && rq[1].x && !rq[0].b[5] && rq[0].a[0] && two_halves(rq[0].a)) r = pop();
            rp_take <= rq.size() != 0 && rq[0].x && !(rp_take && cpu.state == 5'd0);
            if (rq.size() != 0) begin rp_cause <= rq[0].b; rp_value <= rq[0].c; end
            if (rdq.size() != 0) io_rdata <= rdq[0].value;
            if (halt != 0) fail($sformatf("old CPU halted, code %h", halt));
        end
        prev_ret <= ret; prev_pc <= pc; prev_m16 <= m16;
    end

    integer i;
    initial begin
        if (!$value$plusargs("ram=%s", ram_file)) ram_file = "/tmp/ram_guide.hex";
        if (!$value$plusargs("state=%s", state_file)) state_file = "/tmp/state_guide.hex";
        if (!$value$plusargs("flash=%s", flash_file)) flash_file = "sim/fullflash_ddr.hex";
        if (!$value$plusargs("log=%s", log_file)) log_file = "/tmp/vl_stream.txt";
        if ($value$plusargs("n=%d", limit)) ;
        if ($value$plusargs("report=%d", report_every)) ;
        $readmemh(ram_file, ram); $readmemh(flash_file, flash); $readmemh(state_file, state_words);
        fd = $fopen(log_file, "r");
        if (fd == 0) begin $display("cannot open %s", log_file); $finish; end
        repeat (4) @(negedge clk); reset = 0;
        // the 128 KiB boot block, as the launcher's flash download writes it
        for (i = 0; i < 32'h20000; i = i + 2) begin
            boot_load = 1; boot_load_addr = i[16:0];
            boot_load_data = {flash[i >> 3][((i & 7) + 1) * 8 +: 8], flash[i >> 3][(i & 7) * 8 +: 8]};
            @(negedge clk);
        end
        boot_load = 0;
        for (i = 0; i < 68; i = i + 1) begin
            restore_wr = 1; restore_index = i[6:0]; restore_data = state_words[i]; @(negedge clk);
        end
        restore_wr = 0; fill();
        repeat (3) @(negedge clk); hold = 0;
    end
endmodule
