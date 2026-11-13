// System simulation (sim/vl, Verilator): models of the Altera RAM primitives behind
// rtl/r4k's wrappers (black boxes left by sim/vl/ram_stubs.vhd).
`timescale 1ps/1ps
// altdpram as RamMLAB.vhd configures it: write inputs registered on inclock, read address
// and output unregistered. (The Cyclone V MLAB writes on the falling edge after the
// registering edge; with every user on the same clock's rising edge that equals this.)
module sim_ram_mlab #(parameter width = 1, parameter widthad = 1) (
    input  wire               inclock, wren,
    input  wire [width-1:0]   data,
    input  wire [widthad-1:0] wraddress, rdaddress,
    output wire [width-1:0]   q
);
    reg [width-1:0] mem [0:(1<<widthad)-1];
    integer i;
    initial for (i = 0; i < (1<<widthad); i = i + 1) mem[i] = {width{1'b0}};
    always @(posedge inclock) if (wren) mem[wraddress] <= data;
    assign q = mem[rdaddress];
endmodule

// altsyncram BIDIR_DUAL_PORT as dpram.vhd configures it: inputs registered (clock enables
// on the input registers), outputs unregistered, a port reads its own new data while it
// writes; the other port reads the old data on a simultaneous edge (undefined in the part).
// The ports may differ in width (dpram_dif): the narrow port's low address bits pick the
// slice of the wide word, lowest slice first.
module sim_dpram #(parameter addr_width_a = 8, parameter data_width_a = 8,
                   parameter addr_width_b = 8, parameter data_width_b = 8) (
    input  wire                    clock_a, clken_a, wren_a,
    input  wire [addr_width_a-1:0] address_a,
    input  wire [data_width_a-1:0] data_a,
    output reg  [data_width_a-1:0] q_a,
    input  wire                    clock_b, clken_b, wren_b,
    input  wire [addr_width_b-1:0] address_b,
    input  wire [data_width_b-1:0] data_b,
    output reg  [data_width_b-1:0] q_b
);
    localparam W  = data_width_a < data_width_b ? data_width_a : data_width_b;
    localparam RA = data_width_a / W, RB = data_width_b / W;
    localparam DEPTH = (1 << addr_width_a) * RA;
    reg [W-1:0] mem [0:DEPTH-1];
    integer i, ka, kb;
    initial begin
        for (i = 0; i < DEPTH; i = i + 1) mem[i] = {W{1'b0}};
        q_a = {data_width_a{1'b0}}; q_b = {data_width_b{1'b0}};
    end
    always @(posedge clock_a) if (clken_a) begin
        for (ka = 0; ka < RA; ka = ka + 1) begin
            if (wren_a) begin
                mem[address_a * RA + ka] <= data_a[ka*W +: W];
                q_a[ka*W +: W] <= data_a[ka*W +: W];
            end else q_a[ka*W +: W] <= mem[address_a * RA + ka];
        end
    end
    always @(posedge clock_b) if (clken_b) begin
        for (kb = 0; kb < RB; kb = kb + 1) begin
            if (wren_b) begin
                mem[address_b * RB + kb] <= data_b[kb*W +: W];
                q_b[kb*W +: W] <= data_b[kb*W +: W];
            end else q_b[kb*W +: W] <= mem[address_b * RB + kb];
        end
    end
endmodule
