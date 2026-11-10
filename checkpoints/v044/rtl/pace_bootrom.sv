// SPDX-License-Identifier: GPL-3.0-only
// Pace U202 real 128 KiB protected bootloader: 32,768 x 32-bit M10K ROM.
// Single *synchronous* read port. Do not add asynchronous read/view ports;
// they can prevent block-memory inference and explode synthesis complexity.
module pace_bootrom (
    input  wire        clk,
    input  wire [14:0] address,
    output reg  [31:0] q
);
    (* ramstyle = "M10K" *) reg [31:0] words [0:32767];
    initial $readmemh("rom/bootloader_words.hex", words);
    always @(posedge clk) q <= words[address];
endmodule
