`timescale 1ns/1ps

module tb_debug_uart_pending #(parameter EXTRA_FP=0,parameter EXTRA_VIDEO=0,parameter EXTRA_TTX=0);
    reg clk = 0;
    always #10 clk = ~clk;
    reg reset = 1;
    wire tx;
    pace_debug_uart #(.CLOCK_HZ(1152000), .BAUD(115200), .PERIOD(20000),.EXTRA_FP(EXTRA_FP),.EXTRA_VIDEO(EXTRA_VIDEO),.EXTRA_TTX(EXTRA_TTX)) dut (
        .clk(clk), .reset(reset), .pc(32'h8003a929), .instruction(32'd0),
        .retired(32'd0), .ram_writes(32'd0), .mmio_address(32'd0), .mmio_value(32'd0),
        .mmio_read(32'd0), .interrupt_count(32'd0), .guessed_reads(32'd0),
        .fp_state(32'h01234567),
        .video_state(32'h89abcdef),
        .ttx_state(32'hd0050032),
        .mmio_policy(2'd1), .halt_code(8'he5), .mips16(1'b1), .full_flash_loaded(1'b1),
        .ev_valid(1'b0), .ev_we(1'b0), .ev_addr(32'd0), .ev_data(32'd0),
        .prof(512'd0), .tx(tx), .prof_sent(), .prof_fast(1'b1)
    );

    reg sending_previous = 0;
    integer snapshots = 0, profiles = 0;
    always @(posedge clk) begin
        sending_previous <= dut.sending;
        if (dut.sending && !sending_previous) begin
            case (dut.message[dut.BYTES*8-1 -:32])
                "PACE": begin
                    snapshots <= snapshots + 1;
                    if(EXTRA_FP && dut.message[16+(EXTRA_VIDEO ? 96:0)+(EXTRA_TTX ? 96:0)+:96]!=" FP=01234567")$fatal(1,"Controller snapshot missing");
                    if(EXTRA_VIDEO && dut.message[16+(EXTRA_TTX ? 96:0)+:96]!=" MV=89ABCDEF")$fatal(1,"Video snapshot missing");
                    if(EXTRA_TTX && dut.message[111:16]!=" TT=D0050032")$fatal(1,"Teletext snapshot missing");
                end
                "PROF": profiles <= profiles + 1;
            endcase
        end
    end

    initial begin
        repeat (5) @(negedge clk);
        reset = 0;
        repeat (140000) @(negedge clk);
        if (snapshots < 2 || profiles < 2)
            $fatal(1, "Continuous trace starved telemetry, snapshots=%0d profiles=%0d", snapshots, profiles);
        $display("PASS: continuous trace preserved %0d PC/halts snapshots and %0d profile frames", snapshots, profiles);
        $finish;
    end
endmodule
