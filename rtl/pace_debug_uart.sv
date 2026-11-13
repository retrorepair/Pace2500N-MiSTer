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
    // MMIO event trace (diagnostic): each event is queued and sent as the
    // line "Tw aaaaaaaa dddddddd" between telemetry frames. Read-only tap.
    input wire ev_valid, ev_we,
    input wire [31:0] ev_addr, ev_data,
    // Cycle profile (pace_cpu_profile): 16 counters sent as the line
    // "PROF c0 .. c15" right after each telemetry frame.
    input wire [511:0] prof,
    output reg tx=1'b1,
    output reg prof_sent=1'b0,    // pulse: the PROF line was formed (its data sampled)
    input wire prof_fast          // send PROF lines back to back (a frozen trace being read out)
);
    (* ramstyle="M10K" *) reg [64:0] ev_mem[0:511];
    reg [8:0] ev_wr=0, ev_rd=0;
    reg [64:0] ev_q=0;
    reg [1:0] ev_settle=0;
    reg [7:0] last=0;
    wire ev_empty=ev_wr==ev_rd;
    wire ev_full=(ev_wr+9'd1)==ev_rd;
    always @(posedge clk) begin
        ev_q<=ev_mem[ev_rd];
        if(ev_valid && !ev_full) ev_mem[ev_wr]<={ev_we,ev_addr,ev_data};
    end
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
    reg sending=0, byte_active=0, prof_due=0;
    wire [7:0] next_byte=message[(BYTES-1-index)*8 +:8];
    always @(posedge clk) begin
        if(reset) begin
            tx<=1; period_count<=0; baud_count<=0;
            index<=0; bit_index<=0; sending<=0; byte_active<=0;
            ev_wr<=0; ev_rd<=0; ev_settle<=0; prof_due<=0;
        end else begin
            if(ev_valid && !ev_full) ev_wr<=ev_wr+9'd1;
            ev_settle<={ev_settle[0],!ev_empty};
            // One queued MMIO event per line while no telemetry frame is going out.
            prof_sent<=0;
            if(!sending && (prof_due || prof_fast) && period_count!=PERIOD-1) begin
                prof_sent<=1;
                message<={"PROF"," ",hex32(prof[0+:32])," ",hex32(prof[32+:32])," ",hex32(prof[64+:32]),
                    " ",hex32(prof[96+:32])," ",hex32(prof[128+:32])," ",hex32(prof[160+:32]),
                    " ",hex32(prof[192+:32])," ",hex32(prof[224+:32])," ",hex32(prof[256+:32]),
                    " ",hex32(prof[288+:32])," ",hex32(prof[320+:32])," ",hex32(prof[352+:32]),
                    " ",hex32(prof[384+:32])," ",hex32(prof[416+:32])," ",hex32(prof[448+:32]),
                    " ",hex32(prof[480+:32]),8'h0d,8'h0a,{(BYTES-150){8'h20}}};
                sending<=1; index<=0; last<=8'd149; prof_due<=0;
            end else if(!sending && period_count!=PERIOD-1 && !ev_empty && ev_settle==2'b11) begin
                message<={"T",(ev_q[64] ? "1" : "0")," ",hex32(ev_q[63:32])," ",hex32(ev_q[31:0]),8'h0d,8'h0a,{(BYTES-22){8'h20}}};
                sending<=1; index<=0; last<=8'd21;
                ev_rd<=ev_rd+9'd1; ev_settle<=0;
            end
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
                    sending<=1; index<=0; last<=BYTES-1; prof_due<=1;
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
                        if(index==last) sending<=0;
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
