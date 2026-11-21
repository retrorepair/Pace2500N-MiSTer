`timescale 1ns/1ps

// Model the real driver's split receive path. Its ISR clears RX ready before
// SMNTask consumes the software mailbox and writes the next transmit byte.
module tb_front_panel_receipt #(parameter STALL_RETIRE = 0, parameter PAUSE_RETIRE = 0);
    reg clk = 0;
    always #10 clk = ~clk;
    reg reset = 1;
    reg [31:0] retired = 0;
    reg [1:0] retire_phase = 0;
    reg freeze_retire = 0;
    always @(posedge clk) begin
        retire_phase <= retire_phase + 1'b1;
        if (!freeze_retire && (!STALL_RETIRE || retire_phase != 3)) retired <= retired + 1;
    end
    reg request = 0, write = 0;
    reg [31:0] address = 0, data = 0;
    wire [31:0] result, frames;
    wire [7:0] halt;

    pace_guide_peripherals dut (
        .clk(clk), .reset(reset), .hold(1'b0), .retired(retired),
        .io_req(request), .io_we(write), .io_addr(address), .io_wdata(data), .io_size(2'd2),
        .io_rdata(result), .io_ready(), .io_irq(), .key_valid(1'b0), .key_pressed(1'b0),
        .key_code(8'd0), .gpu_start(), .gpu_descriptor(), .osd_root(), .gpu_done(1'b0),
        .transport_irq(1'b0), .mpeg_irq(1'b0), .transport_lock(1'b0), .model_halt(halt),
        .serial_frames(frames), .key_frames(), .timer_acks(), .gpu_acks(), .last_key(),
        .ee_b_addr(16'd0), .ee_b_we(1'b0), .ee_b_wdata(8'd0), .ee_b_q(),
        .ee_a_we(), .ee_a_addr(), .cold(1'b1), .fp_reset_request(), .lsi_bus(),
        .dma5_start(), .dma5_stop(), .dma5_descriptor(), .dma5_done(1'b0)
    );

    task automatic store(input [31:0] register_address, value);
        @(negedge clk);
        address = register_address; data = value; write = 1; request = 1;
        @(negedge clk);
        request = 0; write = 0;
    endtask

    task automatic await_receive;
        integer remaining;
        remaining = 30000;
        while (!(dut.regval(32'hb2009020) & 1) && remaining != 0) begin
            @(negedge clk);
            remaining = remaining - 1;
        end
        if (remaining == 0) $fatal(1, "Controller did not deliver a byte");
    endtask

    task automatic send(input [7:0] value);
        store(32'hb2009010, {24'd0, value});
        store(32'hb200a000, 1);
        store(32'hb200a000, 0);
        await_receive();
        store(32'hb2009020, 0);
    endtask

    task automatic receive_byte(input [7:0] expected);
        store(32'hb2009010, 0);
        store(32'hb200a000, 1);
        store(32'hb200a000, 0);
        await_receive();
        if (dut.serial_rx != expected)
            $fatal(1, "Reply byte %02x, expected %02x", dut.serial_rx, expected);
        store(32'hb2009020, 0);
    endtask

    initial begin
        repeat (5) @(negedge clk);
        reset = 0;
        store(32'hb2009000, 32'h80);
        store(32'hb2009030, 1);
        // 03 01 52 00, with the payload zero escaped, then the terminator.
        send(8'h03); send(8'h01); send(8'h52);
        send(8'h1b); send(8'h00); send(8'h00);
        if (frames != 1 || halt != 0) $fatal(1, "Request framing failed");

        // Request the first reply byte, then leave the GPIO edge delayed as
        // it can be when another interrupt preempts the task.
        store(32'hb2009010, 0);
        store(32'hb200a000, 1);
        freeze_retire = PAUSE_RETIRE;
        await_receive();
        freeze_retire = 0;
        if (dut.serial_rx != 3) $fatal(1, "Wrong reply length byte");
        store(32'hb2009020, 0); // ISR acknowledgement, task has not consumed it
        repeat (20000) @(negedge clk);
        if (dut.regval(32'hb2009020) & 1)
            $fatal(1, "Controller advanced before the receiving task's receipt");

        store(32'hb200a000, 0); // delayed falling edge of the completed transfer
        repeat (1000) @(negedge clk);
        if (dut.regval(32'hb2009020) & 1)
            $fatal(1, "A late clock edge duplicated the receive transfer");

        // SMNTask has now consumed the length byte. Its dummy transmit write
        // releases exactly the next byte, the echoed sequence number.
        store(32'hb2009010, 0);
        store(32'hb200a000, 1);
        // An interrupt can delay GPIO low until exactly the cycle in which
        // the controller finishes its autonomous transfer. That is still the
        // same byte, not permission to clock another one into the mailbox.
        while (!(dut.clock_waiting && dut.clock_delay == 1 && dut.device_tick)) @(negedge clk);
        address = 32'hb200a000; data = 0; write = 1; request = 1;
        @(negedge clk); request = 0; write = 0;
        await_receive();
        if (dut.serial_rx != 1) $fatal(1, "Reply sequence byte was lost");
        if (frames != 1 || halt != 0) $fatal(1, "Reply clocks changed request framing");
        store(32'hb2009020, 0);
        repeat (1000) @(negedge clk);
        if (dut.regval(32'hb2009020) & 1)
            $fatal(1, "Completion-cycle GPIO edge duplicated the receive transfer");
        receive_byte(8'h52); receive_byte(8'h02); receive_byte(8'h00);
        // Only an identity query may run the six-byte identity callback.
        send(8'h03); send(8'h02); send(8'h10);
        send(8'h1b); send(8'h00); send(8'h00);
        receive_byte(8'h08); receive_byte(8'h02); receive_byte(8'h10);
        repeat (6) begin receive_byte(8'h1b); receive_byte(8'h00); end
        receive_byte(8'h00);
        send(8'h03); send(8'h03); send(8'h18);
        send(8'h1b); send(8'h00); send(8'h00);
        receive_byte(8'h02); receive_byte(8'h03); receive_byte(8'h18); receive_byte(8'h00);
        if (frames != 3 || halt != 0) $fatal(1, "Response exchange changed request framing");
        send(8'h03); send(8'h04); send(8'h28);
        send(8'h1b); send(8'h00); send(8'h00);
        receive_byte(8'h03); receive_byte(8'h04); receive_byte(8'h28);
        receive_byte(8'h1b); receive_byte(8'h00); receive_byte(8'h00);
        if (frames != 4 || halt != 0) $fatal(1, "Guide status response changed request framing");
        $display("PASS: task receipt, late/completion-cycle clock, status payload, six-byte identity and heartbeat opcode");
        $finish;
    end
endmodule
