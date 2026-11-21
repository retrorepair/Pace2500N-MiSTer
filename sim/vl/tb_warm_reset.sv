`timescale 1ns/1ps
// Whole-CPU warm-reset regression. A synthetic ROM enables an interrupt;
// reset arrives while its exception redirect is pending. No firmware/state files.
module tb_warm_reset;
    reg clk_sys=0, clk1x=0, clk2x=0;
    always #10 clk_sys=~clk_sys;
    always #14.814815 clk1x=~clk1x;
    always #7.407407 clk2x=~clk2x;
    reg reset=1, irq=0;
    wire req, write;
    wire [28:0] addr;
    wire [7:0] burst;
    reg accept=0, valid=0;
    reg [63:0] data=0;
    reg pending=0;
    reg [28:0] read_addr;
    integer delay_count=0, beats=0, latency=20;
    reg use_tlb=0;
    initial use_tlb=$test$plusargs("tlb");
    initial if ($value$plusargs("lat=%d",latency));
    pace_r4k #(.COUNT_NUM(3),.COUNT_DEN(10)) dut (
        .clk_sys(clk_sys),.clk1x(clk1x),.clk2x(clk2x),
        .reset_sys(reset),.trace_reset(reset),.hold_sys(1'b0),.ckpt_loaded(1'b0),
        .state_wr(1'b0),.state_index(7'd0),.state_data(32'd0),.io_irq(irq),
        .ddr_req(req),.ddr_we(write),.ddr_addr(addr),.ddr_burst(burst),
        .ddr_accept(accept),.ddr_rvalid(valid),.ddr_rdata(data),
        .io_rdata(32'd0),.io_ready(1'b1),.trace_next(1'b0),.trace_trigger(1'b0)
    );
    function automatic [31:0] rom_word(input [31:0] byte_addr);
        case(byte_addr)
            32'h00:rom_word=32'h3c1da000; // lui sp,a000
            32'h04:rom_word=32'h37bd1000; // ori sp,sp,1000
            32'h08:rom_word=32'h3c080040; // lui t0,0040 (BEV)
            32'h0c:rom_word=32'h35080401; // ori t0,t0,0401 (IP2 mask, IE)
            32'h10:rom_word=32'h40886000; // mtc0 t0,Status
            32'h18:rom_word=use_tlb ? 32'h3c081000 : 32'h0bf00006; // virtual fetch / idle
            32'h1c:rom_word=use_tlb ? 32'h01000008 : 32'd0; // jr t0
            32'h380:rom_word=32'h0bf000e0; // exception vector loops
            default:rom_word=0;
        endcase
    endfunction
    function automatic [31:0] bus_word(input [31:0] value);
        bus_word={value[7:0],value[15:8],value[23:16],value[31:24]};
    endfunction
    function automatic [63:0] read_word(input [28:0] qword_addr);
        reg [31:0] byte_addr;
        byte_addr=(qword_addr-29'h06400000)*8;
        read_word={bus_word(rom_word(byte_addr+4)),bus_word(rom_word(byte_addr))};
    endfunction
    // DDR port accepts one transaction, then returns after +lat=N sys clocks.
    // In-flight responses continue through CPU reset, as on the real board.
    always @(posedge clk_sys) begin
        accept<=0;valid<=0;
        if(req && !pending && !accept)begin
            if(write)$fatal(1,"Unexpected ROM write");
            accept<=1;pending<=1;read_addr<=addr;beats<=burst;delay_count<=latency;
        end
        if(pending)begin
            if(delay_count!=0)delay_count<=delay_count-1;
            else begin
                data<=read_word(read_addr);valid<=1;read_addr<=read_addr+1;
                beats<=beats-1;
                if(beats==1)pending<=0;
            end
        end
    end
    integer checked=0, epochs=0;
    reg check_restart=0;
    always @(posedge clk2x) if(check_restart && dut.wb_valid)begin
        if(dut.wb_pc != 32'hbfc00000+checked*4)
            $fatal(1,"Warm restart skipped reset code: instruction %0d PC %08x",checked,dut.wb_pc);
        checked=checked+1;
        if(checked==6)begin check_restart=0;epochs=epochs+1;end
    end
    initial begin
        #1000;reset=0;
        repeat(3)begin
            if(use_tlb)wait(dut.core.core.exceptionstage1);
            else begin
                wait(dut.wb_valid && dut.wb_pc==32'hbfc00018);
                @(negedge clk_sys);irq=1;
                wait(dut.core.core.exception);
            end
            #1;reset=1;irq=0;
            repeat(255)@(negedge clk_sys);
            checked=0;check_restart=1;reset=0;
            wait(!check_restart);
        end
        $display("PASS: %0d whole-CPU warm resets discard pending %s exceptions and execute reset ROM in order",epochs,use_tlb ? "fetch TLB" : "interrupt");
        $finish;
    end
    initial begin #1000000;$fatal(1,"Warm-reset regression timed out");end
endmodule
