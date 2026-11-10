// SPDX-License-Identifier: GPL-3.0-only
// Read-only execution telemetry to the MiSTer HPS UART, 115200 baud, 8N1.
// Snapshot once per second; never stalls or modifies the firmware executor.
module pace_debug_uart #(
    parameter integer CLOCK_HZ=50000000,
    parameter integer BAUD=115200,
    parameter integer PERIOD=CLOCK_HZ
)(
    input wire clk, reset,
    input wire [31:0] pc, instruction, retired, ram_writes,
    input wire [31:0] mmio_address, mmio_value, mmio_read,
    input wire [31:0] interrupt_count, guessed_reads,
    input wire [1:0] mmio_policy,
    input wire [7:0] halt_code,
    input wire mips16, full_flash_loaded,
    output reg tx=1'b1
);
    function automatic [63:0] hex32(input [31:0] value);
        integer n;
        reg [3:0] digit;
        begin
            for(n=0;n<8;n=n+1) begin
                digit=value[31-n*4 -:4];
                hex32[63-n*8 -:8]=(digit<10) ? 8'h30+digit : 8'h41+digit-10;
            end
        end
    endfunction
    // Fixed length frame simplifies framing and bounds all indexing.
    localparam integer BYTES=175;
    localparam integer DIVISOR=CLOCK_HZ/BAUD;
    reg [BYTES*8-1:0] message;
    reg [31:0] period_count=0;
    reg [15:0] baud_count=0;
    reg [7:0] index=0;
    reg [3:0] bit_index=0;
    reg [9:0] frame=10'h3ff;
    reg sending=0, byte_active=0;
    wire [7:0] next_byte=message[(BYTES-1-index)*8 +:8];
    always @(posedge clk) begin
        if(reset) begin
            tx<=1; period_count<=0; baud_count<=0;
            index<=0; bit_index<=0; sending<=0; byte_active<=0;
        end else begin
            if(period_count==PERIOD-1) begin
                period_count<=0;
                if(!sending) begin
                    message<={"PACE PC=",hex32(pc)," IR=",hex32(instruction),
                        " RET=",hex32(retired)," RAM=",hex32(ram_writes),
                        " WA=",hex32(mmio_address)," WD=",hex32(mmio_value),
                        " RD=",hex32(mmio_read)," HALT=",hex32({24'd0,halt_code}),
                        " M16=",hex32({31'd0,mips16})," FLASH=",hex32({31'd0,full_flash_loaded}),
                        " IRQ=",hex32(interrupt_count)," GUESS=",hex32(guessed_reads),
                        " POL=",hex32({30'd0,mmio_policy}),
                        8'h0d,8'h0a};
                    sending<=1; index<=0;
                end
            end else period_count<=period_count+1;
            if(sending) begin
                if(!byte_active) begin
                    frame<={1'b1,next_byte,1'b0}; tx<=0;
                    byte_active<=1; bit_index<=0; baud_count<=DIVISOR-1;
                end else if(baud_count!=0) baud_count<=baud_count-1;
                else begin
                    baud_count<=DIVISOR-1;
                    if(bit_index==9) begin
                        byte_active<=0; tx<=1;
                        if(index==BYTES-1) sending<=0;
                        else index<=index+1;
                    end else begin
                        frame<={1'b1,frame[9:1]};
                        tx<=frame[1]; bit_index<=bit_index+1;
                    end
                end
            end
        end
    end
endmodule
