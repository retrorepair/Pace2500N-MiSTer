// Top-level start-up simulation of the real emu (rtl/Pace2500N_Transport.sv) with the stand-ins
// in sim/emu/stubs.sv. Checks the cold-boot start sequence the system bench (sim/vl/tb_sys.sv)
// does not model: file download into DDR, the guest RAM clear, the hold release and the CPU's
// first instructions, on a DDR model of the MiSTer port (Avalon-MM) that reports protocol misuse.
// Plusargs: +ms=N (simulated milliseconds, default 120), +busy=P (DDR waitrequest P% of cycles),
// plus those of the hps_io stand-in.
`timescale 1ps/1ps
module tb_emu;
    reg CLK_50M = 0; always #10000 CLK_50M = ~CLK_50M;
    reg RESET = 1;
    reg DDRAM_BUSY = 0, DDRAM_DOUT_READY = 0; reg [63:0] DDRAM_DOUT = 0;
    wire DDRAM_CLK, DDRAM_RD, DDRAM_WE; wire [7:0] DDRAM_BURSTCNT, DDRAM_BE; wire [28:0] DDRAM_ADDR; wire [63:0] DDRAM_DIN;
    wire LED_USER;
    emu emu (.CLK_50M(CLK_50M), .RESET(RESET), .LED_USER(LED_USER),
        .DDRAM_CLK(DDRAM_CLK), .DDRAM_BUSY(DDRAM_BUSY), .DDRAM_BURSTCNT(DDRAM_BURSTCNT), .DDRAM_ADDR(DDRAM_ADDR),
        .DDRAM_DOUT(DDRAM_DOUT), .DDRAM_DOUT_READY(DDRAM_DOUT_READY), .DDRAM_RD(DDRAM_RD), .DDRAM_DIN(DDRAM_DIN),
        .DDRAM_BE(DDRAM_BE), .DDRAM_WE(DDRAM_WE),
        .DDRAM2_BUSY(1'b0), .DDRAM2_DOUT(64'd0), .DDRAM2_DOUT_READY(1'b0));

    // ---------------- DDR model: RAM 0x06000000 (16 MiB), flash 0x06400000 (2 MiB), rest counted
    reg [63:0] ram [0:2097151];
    reg [63:0] rom [0:262143];
    integer busypct = 0, lane, errors = 0, outside = 0;
    reg [28:0] wr_addr = 0, rd_addr = 0; reg [7:0] wr_left = 0, wr_burst = 0, rd_left = 0; integer rd_wait = 0;
    longint ram_writes = 0, ram_reads = 0;
    function automatic [63:0] fetch(input [28:0] a);
        if (a >= 29'h06000000 && a < 29'h06200000) fetch = ram[a[20:0]];
        else if (a >= 29'h06400000 && a < 29'h06440000) fetch = rom[a[17:0]];
        else fetch = 64'd0;
    endfunction
    task store(input [28:0] a, input [63:0] d, input [7:0] be);
        for (lane = 0; lane < 8; lane = lane + 1) if (be[lane]) begin
            if (a >= 29'h06000000 && a < 29'h06200000) ram[a[20:0]][lane*8 +: 8] = d[lane*8 +: 8];
            else if (a >= 29'h06400000 && a < 29'h06440000) rom[a[17:0]][lane*8 +: 8] = d[lane*8 +: 8];
        end
        if (!(a >= 29'h06000000 && a < 29'h06200000) && !(a >= 29'h06400000 && a < 29'h06440000)) outside = outside + 1;
    endtask
    always @(posedge DDRAM_CLK) begin
        DDRAM_DOUT_READY <= 0;
        if (rd_left != 0) begin
            if (rd_wait > 0) rd_wait <= rd_wait - 1;
            else begin DDRAM_DOUT <= fetch(rd_addr); DDRAM_DOUT_READY <= 1; rd_addr <= rd_addr + 1; rd_left <= rd_left - 1; ram_reads <= ram_reads + 1; end
        end
        if (!DDRAM_BUSY) begin
            if (DDRAM_RD && DDRAM_WE) begin errors = errors + 1; $display("%0t ps: DDR ERROR: read and write together", $time); end
            if (DDRAM_WE) begin
                if (wr_left == 0) begin
                    if (DDRAM_BURSTCNT == 0) begin errors = errors + 1; $display("%0t ps: DDR ERROR: write burst count 0", $time); end
                    if (DDRAM_BURSTCNT != 1 && errors < 20) $display("%0t ps: DDR note: write burst of %0d at %h", $time, DDRAM_BURSTCNT, DDRAM_ADDR);
                    wr_addr = DDRAM_ADDR; wr_left = DDRAM_BURSTCNT; wr_burst = DDRAM_BURSTCNT;
                end else if (DDRAM_BURSTCNT != wr_burst) begin
                    errors = errors + 1;
                    if (errors < 20) $display("%0t ps: DDR ERROR: burst count changed mid-burst %0d -> %0d", $time, wr_burst, DDRAM_BURSTCNT);
                end
                store(wr_addr, DDRAM_DIN, DDRAM_BE); wr_addr = wr_addr + 1; wr_left = wr_left - 1; ram_writes = ram_writes + 1;
            end
            if (DDRAM_RD) begin
                if (wr_left != 0) begin errors = errors + 1; $display("%0t ps: DDR ERROR: read inside a write burst", $time); end
                if (rd_left != 0) begin errors = errors + 1; $display("%0t ps: DDR ERROR: read while a read is outstanding", $time); end
                rd_addr <= DDRAM_ADDR; rd_left <= DDRAM_BURSTCNT; rd_wait <= 6;
            end
        end
        DDRAM_BUSY <= busypct != 0 && ($urandom % 100) < busypct;
    end

    // ---------------- observation
    longint cyc = 0; integer ms = 120;
    reg holding_q = 1, clearing_q = 0, cleared_q = 0, flash_q = 0, ee_q = 0, dl_q = 0;
    always @(posedge emu.clk_sys) begin
        cyc <= cyc + 1;
        if (emu.ioctl_download != dl_q) begin dl_q <= emu.ioctl_download; $display("%0d us: ioctl_download %b index %0d", cyc / 50, emu.ioctl_download, emu.ioctl_index); end
        if (emu.loaded_flash != flash_q) begin flash_q <= emu.loaded_flash; $display("%0d us: loaded_flash %b", cyc / 50, emu.loaded_flash); end
        if (emu.ee_loading != ee_q) begin ee_q <= emu.ee_loading; $display("%0d us: ee_loading %b", cyc / 50, emu.ee_loading); end
        if (emu.ram_clearing != clearing_q) begin clearing_q <= emu.ram_clearing; $display("%0d us: ram_clearing %b (index %h)", cyc / 50, emu.ram_clearing, emu.clear_index); end
        if (emu.ram_cleared != cleared_q) begin cleared_q <= emu.ram_cleared; $display("%0d us: ram_cleared %b", cyc / 50, emu.ram_cleared); end
        if (emu.holding != holding_q) begin holding_q <= emu.holding; $display("%0d us: holding %b", cyc / 50, emu.holding); end
        if (cyc % 250000 == 0)
            $display("%0d us: cold %b hold %b dl %b flash %b clearing %b idx %h cleared %b ee %b rp %b busy %b | pc %h retired %0d | DDR W %0d R %0d out %0d err %0d",
                     cyc / 50, emu.cold_boot, emu.holding, emu.ioctl_download, emu.loaded_flash, emu.ram_clearing, emu.clear_index,
                     emu.ram_cleared, emu.ee_loading, emu.read_pending, DDRAM_BUSY, emu.pc, emu.retired, ram_writes, ram_reads, outside, errors);
    end
    integer k, nonzero;
    initial begin
        if ($value$plusargs("ms=%d", ms)) ;
        if ($value$plusargs("busy=%d", busypct)) ;
        for (k = 0; k < 2097152; k = k + 1) ram[k] = 64'hdeadbeef_cafef00d;   // an earlier session's RAM
        for (k = 0; k < 262144; k = k + 1) rom[k] = 64'd0;
        #100000 RESET = 0;
        #(longint'(ms) * 1000000000);
        nonzero = 0;
        for (k = 0; k < 2097152; k = k + 4096) if (ram[k] == 64'hdeadbeef_cafef00d) nonzero = nonzero + 1;
        $display("monitor rows 11-15: %h %h %h %h %h", emu.last_ram, emu.mmio_address, emu.mmio_value, emu.mmio_writes, emu.mmio_read);
        $display("END %0d ms: holding %b ram_cleared %b retired %0d pc %h; RAM samples still holding old data: %0d of 512; DDR errors %0d",
                 ms, emu.holding, emu.ram_cleared, emu.retired, emu.pc, nonzero, errors);
        $finish;
    end
endmodule
