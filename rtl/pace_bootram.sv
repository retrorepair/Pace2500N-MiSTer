// SPDX-License-Identifier: GPL-3.0-only
// Pace U202 128 KiB boot block, loaded at run time: the same 32,768 x 32-bit
// M10K and the same single synchronous read port as pace_bootrom, but with no
// initial contents. It is filled from the user's FLASH_U202.bin while the
// launcher downloads it, so the bitstream carries no firmware. The CPU is held
// until that download has finished.
//
// Load port: the download's 16-bit writes (low byte = file byte at load_addr),
// in address order, for U202[000000:020000]. Words are stored big-endian
// 32-bit, exactly as rom/bootloader_words.hex holds them for pace_bootrom.
module pace_bootram (
    input  wire        clk,
    input  wire [14:0] address,
    output reg  [31:0] q,
    input  wire        load,
    input  wire [16:0] load_addr,
    input  wire [15:0] load_data
);
    (* ramstyle = "M10K" *) reg [31:0] words [0:32767];
    reg [15:0] high = 16'd0;
    always @(posedge clk) begin
        if (load && !load_addr[1]) high <= {load_data[7:0], load_data[15:8]};
        if (load && load_addr[1])
            words[load_addr[16:2]] <= {high, load_data[7:0], load_data[15:8]};
        q <= words[address];
    end
endmodule
