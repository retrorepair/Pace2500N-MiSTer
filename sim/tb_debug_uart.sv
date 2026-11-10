`timescale 1ns/1ps
module tb_debug_uart;
    reg clk=0, reset=1;
    always #10 clk=~clk;
    wire tx;
    pace_debug_uart #(.CLOCK_HZ(10000000),.BAUD(1000000),.PERIOD(20000)) DUT(
        .clk(clk),.reset(reset),.pc(32'hbfc01e1c),.instruction(32'h1234abcd),
        .retired(32'h003081ec),.ram_writes(32'd0),
        .mmio_address(32'hb0000040),.mmio_value(32'hff),.mmio_read(32'hb0000002),
        .interrupt_count(32'h123),.guessed_reads(32'h456),.mmio_policy(2'd1),
        .halt_code(8'h03),.mips16(1'b1),.full_flash_loaded(1'b0),.tx(tx));
    localparam [175*8-1:0] EXPECTED={
        "PACE PC=BFC01E1C IR=1234ABCD RET=003081EC RAM=00000000 WA=B0000040 WD=000000FF RD=B0000002 HALT=00000003 M16=00000001 FLASH=00000000 IRQ=00000123 GUESS=00000456 POL=00000001",
        8'h0d,8'h0a};
    integer pass,n,bitn;
    reg [7:0] received;
    initial begin
        repeat(5) @(negedge clk);
        reset=0;
        for(pass=0;pass<2;pass=pass+1) begin
            for(n=0;n<175;n=n+1) begin
                @(negedge tx);
                repeat(15) @(posedge clk);
                for(bitn=0;bitn<8;bitn=bitn+1) begin
                    received[bitn]=tx;
                    repeat(10) @(posedge clk);
                end
                if(tx!==1'b1) $fatal(1,"UART stop bit incorrect");
                if(received!==EXPECTED[(174-n)*8 +:8])
                    $fatal(1,"UART byte %d differs: %h",n,received);
            end
        end
        $display("PASS: UART decodes two complete telemetry snapshots, 8N1");
        $finish;
    end
    initial begin #2000000; $fatal(1,"UART timeout"); end
endmodule
