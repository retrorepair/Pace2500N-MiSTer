// Stand-ins for the parts of the MiSTer build that a top-level start-up simulation cannot use:
// the PLL (clocks from the testbench), hps_io (the MiSTer menu program is played by this file:
// status bits, image mounts with SD block transfers, and file downloads that honour ioctl_wait,
// following the MGL the core is loaded with) and the MPEG video/audio decoders (idle).
// Everything else in emu (rtl/Pace2500N_Transport.sv) is the real RTL.
`timescale 1ps/1ps

module pll(input wire refclk, rst, output reg outclk_0 = 0, outclk_1 = 0, outclk_2 = 0, outclk_3 = 0,
           outclk_4 = 0, outclk_5 = 0, outclk_6 = 0, output reg locked = 0);
    // clk_sys 50 MHz, video 54 MHz, mem 100 MHz, dec 75 MHz, dot 27 MHz, CPU 75/37.5 MHz aligned
    initial begin #1700; forever #10000 outclk_0 = ~outclk_0; end
    initial forever #9259 outclk_1 = ~outclk_1;
    initial forever #5000 outclk_2 = ~outclk_2;
    initial forever #6667 outclk_3 = ~outclk_3;
    initial forever #18519 outclk_4 = ~outclk_4;
    initial forever begin
        #6667 outclk_5 = 1; outclk_6 = 1;
        #6666 outclk_5 = 0;
        #6667 outclk_5 = 1; outclk_6 = 0;
        #6666 outclk_5 = 0;
    end
    initial begin #2000000; locked = 1; end
endmodule

module pace_mpeg_video(
    input wire clk_sys, clk_dec, clk_mem, clk_dot, reset, flush, enable, still,
    input wire [7:0] es_data, input wire es_valid, output wire es_ready,
    output wire [28:0] ddr_addr, output wire [7:0] ddr_burstcnt, output wire ddr_read, ddr_write,
    output wire [63:0] ddr_wdata, output wire [7:0] ddr_be,
    input wire [63:0] ddr_rdata, input wire ddr_rvalid, ddr_waitrequest,
    output wire [7:0] r, g, b, output wire pixel_en, hs, vs, output wire [11:0] h_pos, v_pos,
    output wire video_live, busy, output wire [15:0] pictures, pickups, frames_late, output wire [7:0] vbuf_fill,
    output wire [13:0] horizontal_size, vertical_size,
    output reg seq_evt = 0, gop_evt = 0, pic_evt = 0, field_evt = 0, end_evt = 0,
    output reg [11:0] seq_hsize = 0, seq_vsize = 0, output reg [3:0] seq_aspect = 0,
    output reg [22:0] gop_time_code = 0, output reg [1:0] pic_structure = 0
);
    assign es_ready = 1'b1;
    assign ddr_addr = 0; assign ddr_burstcnt = 1; assign ddr_read = 0; assign ddr_write = 0;
    assign ddr_wdata = 0; assign ddr_be = 0;
    assign {r, g, b} = 0; assign {pixel_en, hs, vs} = 0; assign h_pos = 0; assign v_pos = 0;
    assign {video_live, busy} = 0; assign {pictures, pickups, frames_late} = 0; assign vbuf_fill = 0;
    assign horizontal_size = 0; assign vertical_size = 0;
endmodule

module mp2_decode #(parameter int PCM_AW = 12, parameter CB_INIT = "") (
    input logic clk, rst, wr_en, input logic [7:0] wr_data, output logic full,
    input logic aud_ce, output logic signed [15:0] audio_l, audio_r, output logic aud_valid,
    output logic synced, err_unsupported, output logic [1:0] fs_o,
    output logic dbg_s_nz, dbg_pcm_nz, input logic cp_step, output logic [15:0] cp_q
);
    assign full = 0; assign audio_l = 0; assign audio_r = 0; assign aud_valid = 0; assign synced = 0;
    assign err_unsupported = 0; assign fs_o = 0; assign dbg_s_nz = 0; assign dbg_pcm_nz = 0; assign cp_q = 0;
endmodule

// The MiSTer menu program, for this simulation. Plusargs:
//   +status=HEX     OSD status bits (default 0: on the cold-boot branch, "Boot: Cold from flash")
//   +flash=HEX      flash image as 64-bit DDR words (default sim/fullflash_ddr.hex)
//   +noeeprom       do not mount the EEPROM save file (the MGL mounts it first)
module hps_io #(parameter CONF_STR = "", CONF_STR_BRAM = 0, PS2DIV = 0, WIDE = 0, VDNUM = 1, BLKSZ = 2,
                PS2WE = 0, STRLEN = 0, F12KEYMOD = 0) (
    input clk_sys, inout [45:0] HPS_BUS,
    output [1:0] buttons, output reg [127:0] status = 0, input [127:0] status_in, input status_set,
    input [15:0] status_menumask, output reg [10:0] ps2_key = 0, output reg [64:0] RTC = 0,
    input video_rotated, new_vmode,
    output reg ioctl_download = 0, ioctl_wr = 0, output reg [15:0] ioctl_index = 0,
    output reg [26:0] ioctl_addr = 0, output reg [15:0] ioctl_dout = 0, input ioctl_wait,
    input ioctl_upload_req, input [7:0] ioctl_upload_index, input [15:0] ioctl_din,
    output reg [VDNUM-1:0] img_mounted = 0, output reg img_readonly = 0, output reg [63:0] img_size = 0,
    input [31:0] sd_lba[VDNUM], input [5:0] sd_blk_cnt[VDNUM], input [VDNUM-1:0] sd_rd, sd_wr,
    output reg [VDNUM-1:0] sd_ack = 0, output reg [12:0] sd_buff_addr = 0, output reg [15:0] sd_buff_dout = 0,
    input [15:0] sd_buff_din[VDNUM], output reg sd_buff_wr = 0
);
    assign buttons = 2'b00;
    reg [63:0] flash [0:262143];
    reg [7:0] eeprom_file [0:65535];
    reg [1023:0] flash_file;
    integer i, w, slot;
    reg [127:0] status_arg = 0;
    reg serving = 0;
    // SD block transfers for both image slots (core reads the EEPROM file on mount, and writes
    // back changed blocks later; writes are accepted and kept in eeprom_file).
    always begin
        @(posedge clk_sys);
        if (sd_rd != 0 || sd_wr != 0) begin
            slot = sd_rd[1] || sd_wr[1] ? 1 : 0;
            repeat (7) @(posedge clk_sys);
            sd_ack[slot] <= 1; sd_buff_addr <= 0;
            @(posedge clk_sys);
            for (w = 0; w < 256 * (sd_blk_cnt[slot] + 1); w = w + 1) begin
                sd_buff_addr <= w[12:0];
                if (sd_rd[slot]) begin
                    sd_buff_dout <= slot == 1 ? {eeprom_file[(sd_lba[slot] * 512 + w * 2 + 1) & 16'hffff],
                                                 eeprom_file[(sd_lba[slot] * 512 + w * 2) & 16'hffff]} : 16'd0;
                    @(posedge clk_sys); sd_buff_wr <= 1; @(posedge clk_sys); sd_buff_wr <= 0; repeat (3) @(posedge clk_sys);
                end else begin
                    repeat (5) @(posedge clk_sys);
                    if (slot == 1) {eeprom_file[(sd_lba[1] * 512 + w * 2 + 1) & 16'hffff],
                                    eeprom_file[(sd_lba[1] * 512 + w * 2) & 16'hffff]} = sd_buff_din[1];
                end
            end
            @(posedge clk_sys); sd_ack <= 0;
            repeat (3) @(posedge clk_sys);
        end
    end
    task download(input [15:0] index, input integer bytes);
        integer a;
        begin
            @(posedge clk_sys); ioctl_index <= index; ioctl_download <= 1;
            repeat (4) @(posedge clk_sys);
            for (a = 0; a < bytes; a = a + 2) begin
                while (ioctl_wait) @(posedge clk_sys);
                ioctl_addr <= a[26:0];
                ioctl_dout <= {flash[a >> 3][((a + 1) & 7) * 8 +: 8], flash[a >> 3][(a & 7) * 8 +: 8]};
                ioctl_wr <= 1; @(posedge clk_sys); ioctl_wr <= 0;
                repeat (2) @(posedge clk_sys);
            end
            repeat (4) @(posedge clk_sys); ioctl_download <= 0;
            $display("%0t ps: menu: download index %0d done (%0d bytes)", $time, index, bytes);
        end
    endtask
    initial begin
        if (!$value$plusargs("flash=%s", flash_file)) flash_file = "sim/fullflash_ddr.hex";
        $readmemh(flash_file, flash);
        for (i = 0; i < 65536; i = i + 1) eeprom_file[i] = 8'hff;
        if ($value$plusargs("status=%h", status_arg)) ;
        status = status_arg;
        // the MGL: <file delay="1" type="s" index="1" EEPROM.bin>, <file type="f" index="0" FLASH>
        repeat (200) @(posedge clk_sys);
        if (!$test$plusargs("noeeprom")) begin
            img_size <= 65536; img_mounted <= 2'b10; @(posedge clk_sys); img_mounted <= 0;
            $display("%0t ps: menu: EEPROM.bin mounted", $time);
            repeat (2000) @(posedge clk_sys);
        end
        download(16'd0, 2097152);
        // <file delay="1" type="s" index="0" path="/tmp/pace_live.ts"/> (blocks read back as zero)
        if (!$test$plusargs("nolive")) begin
            repeat (50) @(posedge clk_sys);
            img_size <= 64'd67108864; img_mounted <= 2'b01; @(posedge clk_sys); img_mounted <= 0;
            $display("%0t ps: menu: live ring mounted", $time);
        end
    end
endmodule
