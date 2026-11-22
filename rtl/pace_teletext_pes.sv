// SPDX-License-Identifier: GPL-3.0-only
// Passive tap for the PC service's bounded, canonical EN300472 PES packets.
// No A/V backpressure. Bad/unsupported TS packets are discarded atomically.
// This is a transport-to-VBI bridge, not an emulation of EMMA B0008xxx.
module pace_teletext_pes #(
    parameter [12:0] PID=13'h1ef0
)(
    input wire clk,reset,strobe,packet_start,
    input wire [7:0] data,
    input wire space,
    output wire valid,
    output wire [7:0] value,
    output reg [15:0] accepted=0,dropped=0
);
    (* ramstyle="MLAB, no_rw_check" *) reg [7:0] packet[0:187];
    reg [7:0] pos=0;
    reg good=0;
    reg [12:0] pid=0;
    reg drain=0;
    reg [1:0] unit=0;
    reg [5:0] byte_pos=0;
    reg [2:0] units=0,drain_units=0;
    function automatic [7:0] reverse(input [7:0] v);
        integer b;begin for(b=0;b<8;b=b+1)reverse[b]=v[7-b];end
    endfunction
    wire [7:0] base=unit==0 ? 8'd54:unit==1 ? 8'd100:8'd146;
    wire chosen=drain_units[unit];
    assign valid=drain && chosen;
    assign value=byte_pos==0 || byte_pos==1 ? 8'h55:byte_pos==2 ? 8'h27:reverse(packet[base+byte_pos-6'd3]);
    // Three output lines cost135 clocks; even back-to-back188-byte TS packets
    // cannot overwrite a byte before it has been emitted (first data byte54).
    always @(posedge clk)begin
        if(reset)begin pos<=0;good<=0;pid<=0;drain<=0;unit<=0;byte_pos<=0;units<=0;drain_units<=0;accepted<=0;dropped<=0;end
        else begin
            if(drain)begin
                if(byte_pos==44)begin
                    byte_pos<=0;
                    if(unit==2)drain<=0;
                    else unit<=unit+1'b1;
                end else byte_pos<=byte_pos+1'b1;
            end
            if(strobe)begin
                if(packet_start)begin
                    pos<=1;good<=data==8'h47;units<=0;
                end else if(pos!=0)begin
                    packet[pos]<=data;
                    pos<=pos==187 ? 0:pos+1'b1;
                    case(pos)
                        1:begin pid[12:8]<=data[4:0];if(data[7:5]!=3'b010)good<=0;end
                        2:begin pid[7:0]<=data;if({pid[12:8],data}!=PID)good<=0;end
                        3:if(data[7:4]!=4'h1)good<=0; // payload only, unscrambled
                        4,5,8:if(data!=0)good<=0;
                        6:if(data!=1)good<=0;
                        7:if(data!=8'hbd)good<=0;
                        9:if(data!=8'hb2)good<=0;
                        10:if(data!=8'h84)good<=0; // data_alignment_indicator=1
                        11:if(data!=0)good<=0;
                        12:if(data!=8'h24)good<=0;
                        49:if(data<8'h10 || data>8'h1f)good<=0;
                        50:units[0]<=data==2 || data==3;
                        96:units[1]<=data==2 || data==3;
                        142:units[2]<=data==2 || data==3;
                        51,97,143:if(data!=44)good<=0;
                        53:if(units[0] && data!=8'he4)good<=0;
                        99:if(units[1] && data!=8'he4)good<=0;
                        145:if(units[2] && data!=8'he4)good<=0;
                        default:begin end
                    endcase
                    if(pos==187 && pid==PID)begin
                        if(good && space && !drain && units!=0)begin
                            drain<=1;drain_units<=units;unit<=0;byte_pos<=0;accepted<=accepted+1'b1;
                        end else dropped<=dropped+1'b1;
                    end
                end
            end
        end
    end
endmodule
