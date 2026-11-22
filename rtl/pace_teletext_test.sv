// SPDX-License-Identifier: GPL-3.0-only
// Experimental, reduced-amplitude monochrome VBI on the existing digital
// CSync pin. RGB/VS are untouched. The external cable/TV filters a one-bit
// black pedestal (50/127 of peak); actual TV decoding is NOT guaranteed.
// Native 54 MHz / 625-line RGB only. F11 opens a nonpersistent 30s window.
module pace_teletext_test #(
    parameter integer TEST_CYCLES=1620000000,
    parameter integer LIVE=0,
    parameter ROM_FILE="rom/teletext_test100.hex"
)(
    input wire clk, reset, allowed, trigger_toggle,
    input wire hsync, vsync, sync_n, // HS/VS active high; physical sync active low
    input wire live_enable,stream_reset,packet_available,
    input wire [7:0] packet_data,
    output wire packet_read,
    output wire hs_out,
    output wire [31:0] debug_state
);
    (* ramstyle="M10K" *) reg [7:0] rom[0:1124];
    initial $readmemh(ROM_FILE,rom);
    reg [10:0] rom_addr=0;
    reg [7:0] rom_q=0;
    always @(posedge clk) rom_q<=rom[rom_addr];
    (* async_reg="true" *) reg [1:0] trigger_sync=0;
    reg trigger_old=0, hs_old=0, vs_old=0;
    reg [12:0] line_cycle=0;
    reg [9:0] field_line=0;
    reg [1:0] good_lines=0;
    reg [30:0] remaining=0;
    reg [6:0] pedestal=0;
    wire [7:0] pedestal_sum={1'b0,pedestal}+8'd50;
    wire black_bit=pedestal_sum>=8'd127;
    wire locked=good_lines==2;
    reg [24:0] alive=0;
    (* async_reg="true" *) reg [1:0] reset_sync=0,enable_sync=0;
    wire live_on=LIVE!=0 && enable_sync[1] && alive!=0 && remaining==0;
    wire active=(remaining!=0 || live_on) && allowed && locked && !reset;
    wire hs_edge=hsync && !hs_old;
    wire trigger_edge=trigger_sync[1]!=trigger_old;
    reg busy=0;
    reg from_stream=0;
    reg [7:0] tx_byte=0;
    reg [8:0] phase=0;
    wire [9:0] next_phase={1'b0,phase}+10'd37;
    reg [2:0] bit_index=0;
    reg [5:0] byte_index=0;
    reg [4:0] row=0;
    reg [15:0] sent=0;
    // Multiply by 45 using constant shifts/adds, never a scarce DSP.
    wire [10:0] row_base=({6'd0,row}<<5)+({6'd0,row}<<3)+({6'd0,row}<<2)+{6'd0,row};
    wire line_start=active && !busy && !hs_edge && !trigger_edge && line_cycle==13'd554;
    wire start_stream=line_start && live_on && !reset_sync[1] && field_line>=8 && field_line<=18 && packet_available;
    wire next_stream=busy && from_stream && next_phase>=10'd288 && bit_index==7 && byte_index<44;
    assign packet_read=LIVE!=0 && !reset && !reset_sync[1] && active && !hs_edge && !trigger_edge && (start_stream || next_stream);
    assign hs_out=active ? (sync_n && ((busy && tx_byte[0]) || black_bit)) : sync_n;
    assign debug_state={active,locked,busy,(remaining!=0),4'd0,3'd0,row,sent};
    always @(posedge clk) begin
        trigger_sync<={trigger_sync[0],trigger_toggle};
        trigger_old<=trigger_sync[1];
        hs_old<=hsync;
        vs_old<=vsync;
        reset_sync<={reset_sync[0],stream_reset};enable_sync<={enable_sync[0],live_enable};
        if(LIVE!=0 && packet_available && enable_sync[1])alive<=25'd27000000;
        else if(alive!=0)alive<=alive-1'b1;
        pedestal<=black_bit ? pedestal_sum-8'd127 : pedestal_sum[6:0];
        if(reset) begin
            trigger_sync<=0;trigger_old<=0;hs_old<=0;vs_old<=0;
            line_cycle<=0;field_line<=0;good_lines<=0;remaining<=0;
            busy<=0;row<=0;sent<=0;rom_addr<=0;pedestal<=0;
            tx_byte<=0;phase<=0;byte_index<=0;bit_index<=0;
            from_stream<=0;alive<=0;reset_sync<=0;enable_sync<=0;
        end else begin
            if(line_cycle<13'd7000)line_cycle<=line_cycle+1'b1;
            if(line_cycle>13'd3460)good_lines<=0;
            if(hs_edge)begin
                line_cycle<=0;
                if(line_cycle==13'd3455)begin
                    if(good_lines!=2)good_lines<=good_lines+1'b1;
                end else good_lines<=0;
                field_line<=field_line+1'b1;
                rom_addr<=row_base;
            end
            if(vsync && !vs_old)field_line<=0;
            if(remaining!=0)remaining<=remaining-1'b1;
            if(!allowed)remaining<=0;
            if(trigger_edge && allowed)begin
                remaining<=remaining!=0 ? 31'd0 : TEST_CYCLES;
                row<=0;sent<=0;rom_addr<=0;
            end
            if(!active || hs_edge || trigger_edge || (LIVE!=0 && reset_sync[1] && busy && from_stream))begin
                busy<=0;phase<=0;bit_index<=0;byte_index<=0;
            end else if(start_stream)begin
                busy<=1;from_stream<=1;tx_byte<=packet_data;phase<=0;bit_index<=0;byte_index<=0;
            end else if(line_start && remaining!=0 && field_line==10'd16)begin
                busy<=1;from_stream<=0;tx_byte<=rom_q;phase<=0;bit_index<=0;byte_index<=0;
            end else if(busy)begin
                if(next_phase>=10'd288)begin
                    phase<=next_phase-10'd288;
                    bit_index<=bit_index+1'b1;
                    if(!from_stream && bit_index==3'd6 && byte_index<6'd44)
                        rom_addr<=row_base+byte_index+11'd1;
                    if(bit_index==3'd7)begin
                        if(byte_index==6'd44)begin
                            busy<=0;sent<=sent+1'b1;
                            if(!from_stream)row<=row==5'd24 ? 5'd0 : row+1'b1;
                        end else begin
                            tx_byte<=from_stream ? packet_data:rom_q;byte_index<=byte_index+1'b1;
                        end
                    end else tx_byte<={1'b0,tx_byte[7:1]};
                end else phase<=next_phase[8:0];
            end
        end
    end
endmodule
