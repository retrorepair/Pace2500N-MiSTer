`timescale 1ns/1ps
// An aborted I2C read must not complete against the next transaction's address.
module tb_i2c_abort;
    reg clk=0;always #10 clk=~clk;
    reg reset=1,ee_write=0;
    reg [31:0] retired=0;reg freeze_retire=0;
    always @(posedge clk)if(!freeze_retire)retired<=retired+1;
    reg request=0,write=0;
    reg [31:0] address=0,data=0;
    wire [31:0] result,frames;wire [7:0] halt;
    pace_guide_peripherals dut (
        .clk(clk), .reset(reset), .hold(1'b0), .retired(retired),
        .io_req(request), .io_we(write), .io_addr(address), .io_wdata(data), .io_size(2'd2),
        .io_rdata(result), .io_ready(), .io_irq(), .key_valid(1'b0), .key_pressed(1'b0),
        .key_code(8'd0), .gpu_start(), .gpu_descriptor(), .osd_root(), .gpu_done(1'b0),
        .transport_irq(1'b0), .mpeg_irq(1'b0), .transport_lock(1'b0), .model_halt(halt),
        .serial_frames(frames), .key_frames(), .timer_acks(), .gpu_acks(), .last_key(),
        .ee_b_addr(16'h1234), .ee_b_we(ee_write), .ee_b_wdata(8'ha5), .ee_b_q(),
        .ee_a_we(), .ee_a_addr(), .cold(1'b1), .fp_reset_request(), .lsi_bus(),
        .dma5_start(), .dma5_stop(), .dma5_descriptor(), .dma5_done(1'b0)
    );

    task automatic store(input [31:0] register_address, value);
        @(negedge clk);
        address = register_address; data = value; write = 1; request = 1;
        @(negedge clk);
        request = 0; write = 0;
    endtask

    task automatic complete;
        integer remaining;
        remaining=200;
        while(!(dut.regval(32'hb2006050)&1) && remaining!=0)begin
            @(negedge clk);remaining=remaining-1;
        end
        if(remaining==0)$fatal(1,"I2C completion missing");
        store(32'hb2006050,0);
    endtask
    task automatic begin_read;
        store(32'hb2006000,32'h9a);
        store(32'hb2006040,32'ha1);complete();
        store(32'hb2006000,32'ha8);
    endtask
    initial begin
        repeat(5)@(negedge clk);reset=0;
        ee_write=1;@(negedge clk);ee_write=0;
        begin_read();
        // Timeout/abort recovery, then the next EEPROM write-address phase.
        store(32'hb2006000,32'h99);
        store(32'hb2006000,32'h9a);
        store(32'hb2006040,32'ha0);
        repeat(100)@(negedge clk);
        if(halt!=0)$fatal(1,"Aborted receive leaked into the next write-address phase: halt %02x",halt);
        if(dut.ee_pointer!=0)$fatal(1,"Aborted receive advanced EEPROM pointer");
        // A repeated START also replaces an unfinished receive operation.
        begin_read();
        store(32'hb2006000,32'h9a);
        store(32'hb2006040,32'ha0);
        repeat(100)@(negedge clk);
        if(halt!=0)$fatal(1,"Repeated START retained an old receive");
        // Normal random-access read still returns the loaded EEPROM byte.
        store(32'hb2006050,0);
        store(32'hb2006040,32'h12);complete();
        store(32'hb2006040,32'h34);complete();
        begin_read();freeze_retire=1;complete();freeze_retire=0;
        if(dut.regval(32'hb2006040)!=32'ha5 || dut.ee_pointer!=16'h1235)
            $fatal(1,"Normal EEPROM read changed: data %02x pointer %04x",dut.regval(32'hb2006040),dut.ee_pointer);
        store(32'hb2006000,32'h99);
        // Unsupported reads must still be visible; do not hide them with zeros.
        store(32'hb2006000,32'h9a);
        store(32'hb2006040,32'ha3);complete();
        store(32'hb2006000,32'ha8);
        repeat(100)@(negedge clk);
        if(halt!=8'he7)$fatal(1,"Unsupported I2C read no longer reports E7");
        $display("PASS: STOP/START cancel pending receive; EEPROM read completes with CPU paused; unsupported-read diagnostics retained");
        $finish;
    end
endmodule
