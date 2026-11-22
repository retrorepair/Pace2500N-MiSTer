// SPDX-License-Identifier: GPL-3.0-only
// 2KiB byte FIFO across system/video clocks. Admission reserves all135 bytes
// of a canonical TS packet, so overflow cannot expose a truncated VBI line.
module pace_teletext_fifo(
    input wire wrclk,rdclk,reset,wrreq,rdreq,
    input wire [7:0] data,
    output wire [7:0] q,
    output wire space,available,
    output wire [10:0] rdusedw
);
    wire [10:0] wrusedw;
    wire full,empty;
    assign space=!full && wrusedw<=11'd1850;
    assign available=!empty && rdusedw>=11'd45;
    dcfifo #(.intended_device_family("Cyclone V"),.lpm_numwords(2048),
        .lpm_width(8),.lpm_widthu(11),.lpm_showahead("ON"),.overflow_checking("ON"),
        .underflow_checking("ON"),.rdsync_delaypipe(4),.wrsync_delaypipe(4),
        .use_eab("ON"),.read_aclr_synch("ON"),.write_aclr_synch("ON")) storage(
        .aclr(reset),.wrclk(wrclk),.rdclk(rdclk),.wrreq(wrreq && !full),
        .rdreq(rdreq && !empty),.data(data),.q(q),.wrfull(full),.rdempty(empty),
        .wrusedw(wrusedw),.rdusedw(rdusedw));
endmodule
