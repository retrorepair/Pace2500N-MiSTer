`timescale 1ns/1ps

// Exercise the wrapper's asynchronous request/response bridge. The CPU pins
// are driven directly, so this test needs no ROM, checkpoint, or CPU model.
// Compile with Icarus -i (the CPU instance is intentionally not elaborated).
module tb_r4k_reset_bus;
    reg clk_sys=0, clk1x=0, clk2x=0;
    always #10 clk_sys=~clk_sys;
    always #14 clk1x=~clk1x;
    always #7 clk2x=~clk2x;
    reg reset=1, hold_cpu=0, ready=0;
    reg ddr_accept=0, ddr_valid=0;
    reg [63:0] ddr_data=0;
    wire request, ddr_request;
    wire [28:0] ddr_address;
    integer completions=0;
    always @(posedge clk1x) if (dut.mem_done) completions<=completions+1;
    pace_r4k dut (
        .clk_sys(clk_sys), .clk1x(clk1x), .clk2x(clk2x),
        .reset_sys(reset), .trace_reset(reset), .hold_sys(hold_cpu), .ckpt_loaded(1'b0),
        .state_wr(1'b0), .state_index(7'd0), .state_data(32'd0), .io_irq(1'b0),
        .ddr_req(ddr_request), .ddr_addr(ddr_address),
        .ddr_accept(ddr_accept), .ddr_rvalid(ddr_valid), .ddr_rdata(ddr_data),
        .io_req(request), .io_rdata(32'h12345678), .io_ready(ready),
        .trace_next(1'b0), .trace_trigger(1'b0)
    );
    task automatic issue;
        @(negedge clk1x); force dut.mem_request=1;
        @(negedge clk1x); force dut.mem_request=0;
        wait(request);
    endtask
    task automatic issue_read;
        @(negedge clk1x); force dut.mem_request=1;
        @(negedge clk1x); force dut.mem_request=0;
        wait(ddr_request);
        @(negedge clk_sys); ddr_accept=1;
        @(negedge clk_sys); ddr_accept=0;
    endtask
    initial begin
        force dut.mem_request=0; force dut.mem_address=32'h12006040;
        force dut.mem_rnw=0; force dut.mem_req64=0; force dut.mem_size=2;
        force dut.mem_writeMask=8'h0f; force dut.mem_dataWrite=64'h0000000018000000;
        force dut.mem_line_write=0; force dut.mem_line_data=0; force dut.mem_line_bytes=0;
        force dut.wb_valid=0;
        #300; reset=0; #3000;
        issue(); // Peripheral has not accepted this transaction.
        @(negedge clk_sys); reset=1;
        #300; reset=0;
        // No CPU request has been made since reset. The pre-reset write must
        // never reach the peripheral again or complete a post-reset request.
        repeat(160) begin
            @(negedge clk_sys);
            if(request) $fatal(1,"Warm reset replayed the old peripheral write");
        end
        issue();
        @(negedge clk_sys); ready=1;
        @(negedge clk_sys); ready=0;
        #1000;
        if(completions!=1 || request) $fatal(1,"Fresh request did not complete exactly once");
        // A download hold resets the CPU too. Its completed transaction must
        // not be replayed when the CPU's request toggle returns to zero.
        @(negedge clk_sys); hold_cpu=1;
        #2000; hold_cpu=0;
        repeat(160) begin
            @(negedge clk_sys);
            if(request) $fatal(1,"CPU hold replayed a completed peripheral write");
        end
        force dut.mem_rnw=1; force dut.mem_address=32'h00000000;
        issue_read();
        @(negedge clk_sys); reset=1;
        #300; reset=0;
        // The old DDR response may drain after reset. It must not answer a
        // newly started CPU fetch or provoke a duplicate external request.
        @(negedge clk_sys); ddr_valid=1; ddr_data=64'haaaaaaaaaaaaaaaa;
        @(negedge clk_sys); ddr_valid=0;
        repeat(160) begin
            @(negedge clk_sys);
            if(request || ddr_request) $fatal(1,"Reset replayed the old DDR request");
        end
        force dut.mem_address=32'h00000020;
        issue_read();
        if(ddr_address!=29'h06000004) $fatal(1,"Fresh read retained the pre-reset address");
        repeat(6) @(negedge clk_sys);
        ddr_valid=1; ddr_data=64'h1122334455667788;
        @(negedge clk_sys); ddr_valid=0;
        #1000;
        if(completions!=2 || dut.mem_dataRead!=64'h0000000055667788)
            $fatal(1,"Fresh read consumed a stale response");
        $display("PASS: warm reset and hold cancel stale MMIO/DDR; fresh write and read complete once");
        $finish;
    end
    initial begin #50000; $fatal(1,"Reset bridge test timed out"); end
endmodule
