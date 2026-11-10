// SPDX-License-Identifier: GPL-3.0-only
// MiSTer generic emu top: ORIGINAL Pace flash execution + 576i CRT monitor.
// WARNING: not a functional Sky Digibox; decoder/EMMA hardware remains unknown.
module emu (
`include "sys/emu_ports.vh"
);
localparam CONF_STR={
    "Pace2500N;;",
    "F0,BIN,Load FLASH_U202.bin;",
    "O[2:1],Unknown hardware read,Halt,Return zero,Return FFFF,Return one;",
    "-;",
    "R0,Restart actual firmware;",
    "V,0.4.4"
};

// The MiSTer shell feeds CLK_VIDEO into PLL-only clock-select inputs.
// Keep all core logic on the same PLL-derived 50 MHz domain.
wire clk_sys, pll_locked;
pll pll (.refclk(CLK_50M), .rst(1'b0), .outclk_0(clk_sys), .locked(pll_locked));

// Unused platform interfaces: MiSTer sys_top remains responsible for
// pinout, HPS bus, and video/composite sync on the analogue board.
assign ADC_BUS='Z;
assign USER_OUT='1;
assign {UART_RTS,UART_DTR}=2'b00;
assign {SD_SCK,SD_MOSI,SD_CS}='Z;
assign {SDRAM_DQ,SDRAM_A,SDRAM_BA,SDRAM_CLK,SDRAM_CKE,
        SDRAM_DQML,SDRAM_DQMH,SDRAM_nWE,SDRAM_nCAS,
        SDRAM_nRAS,SDRAM_nCS}='Z;
`ifdef MISTER_DUAL_SDRAM
assign {SDRAM2_DQ,SDRAM2_A,SDRAM2_BA,SDRAM2_CLK,SDRAM2_nRAS,
        SDRAM2_nCAS,SDRAM2_nWE,SDRAM2_nCS}='Z;
`endif
`ifdef MISTER_FB
assign FB_EN=1'b0;
assign FB_FORMAT=5'd0;
assign FB_WIDTH=12'd0;
assign FB_HEIGHT=12'd0;
assign FB_BASE=32'd0;
assign FB_STRIDE=14'd0;
assign FB_FORCE_BLANK=1'b0;
`ifdef MISTER_FB_PALETTE
assign {FB_PAL_CLK,FB_PAL_ADDR,FB_PAL_DOUT,FB_PAL_WR}='0;
`endif
`endif
assign VGA_SL=2'b00;
assign VGA_SCALER=1'b0;
assign VGA_DISABLE=1'b0;
assign HDMI_FREEZE=1'b0;
assign HDMI_BLACKOUT=1'b0;
assign HDMI_BOB_DEINT=1'b1; // Interlaced field bob for HDMI fallback
assign LED_POWER=2'b00;
assign LED_DISK=2'b00;
assign AUDIO_L=16'd0;
assign AUDIO_R=16'd0;
assign AUDIO_S=1'b1;
assign AUDIO_MIX=2'b00;
assign VIDEO_ARX=13'd4;
assign VIDEO_ARY=13'd3;
assign BUTTONS=2'b00;
assign DDRAM_CLK=clk_sys;
assign DDRAM_BURSTCNT=8'd1;

wire [1:0] buttons;
wire [127:0] status;
wire [31:0] joystick_0;
wire [10:0] ps2_key;
wire forced_scandoubler;
wire ioctl_download,ioctl_wr;
wire [15:0] ioctl_index,ioctl_dout;
wire [26:0] ioctl_addr;
wire ioctl_wait;
hps_io #(.CONF_STR(CONF_STR),.WIDE(1)) io (
    .clk_sys(clk_sys),.HPS_BUS(HPS_BUS),
    .buttons(buttons),.status(status),.status_in(status),
    .status_set(1'b0),.status_menumask(16'h0000),
    .joystick_0(joystick_0),.ps2_key(ps2_key),
    .forced_scandoubler(forced_scandoubler),
    .video_rotated(1'b0),.new_vmode(1'b0),
    .ioctl_download(ioctl_download),.ioctl_wr(ioctl_wr),
    .ioctl_index(ioctl_index),.ioctl_addr(ioctl_addr),
    .ioctl_dout(ioctl_dout),.ioctl_wait(ioctl_wait),
    .ioctl_upload_req(1'b0),.ioctl_upload_index(8'h00),.ioctl_din(16'h0000),
    .sd_lba('{32'd0}),.sd_blk_cnt('{6'd0}),.sd_rd(1'b0),.sd_wr(1'b0),
    .sd_buff_din('{16'h0000}),.sd_buff_wr()
);

wire cpu_mem_req,cpu_mem_we;
wire [28:0] cpu_mem_addr;
wire [63:0] cpu_mem_data;
wire [7:0] cpu_mem_be;
wire cpu_accept,cpu_rvalid;
wire [31:0] pc,inst,retired,ram_writes,last_ram,mmio_address,
            mmio_value,mmio_read,mmio_writes,guessed_reads;
wire [7:0] halt_code;
wire mips16,reach16;
pace_debug_uart telemetry (
    .clk(clk_sys),.reset(!pll_locked),.tx(UART_TXD),
    .pc(pc),.instruction(inst),.retired(retired),.ram_writes(ram_writes),
    .mmio_address(mmio_address),.mmio_value(mmio_value),.mmio_read(mmio_read),
    .halt_code(halt_code),.mips16(mips16),.full_flash_loaded(full_flash_loaded)
);
reg full_flash_loaded=1'b0;
reg was_downloading=1'b0;
reg saw_flash_end=1'b0;
// Core is usable from the internal 128 KiB bootloader immediately;
// Loading full 2 MiB is required to progress into application firmware.
always @(posedge clk_sys)begin
    was_downloading<=ioctl_download;
    if(ioctl_download && ioctl_wr && ioctl_index==0 &&
       ioctl_addr>=27'd2097150) saw_flash_end<=1'b1;
    if(was_downloading && !ioctl_download)begin
        full_flash_loaded<=saw_flash_end;
        saw_flash_end<=1'b0;
    end
end

// HPS writes the original binary into DDR3 at byte 0x32000000.
// ioctl_dout[7:0] is the earlier source byte. DDR3 byte lanes are little
// endian; the CPU explicitly swaps 16/32-bit accesses to emulate MIPS BE.
wire loading = ioctl_download && ioctl_index==0;
wire download_store=loading && ioctl_wr && !DDRAM_BUSY;
assign ioctl_wait = DDRAM_BUSY || (cpu_mem_req && !ioctl_download);
assign cpu_accept = cpu_mem_req && !DDRAM_BUSY && !ioctl_download;
assign cpu_rvalid = DDRAM_DOUT_READY;
assign DDRAM_ADDR=download_store ?
   (29'h06400000 + {8'd0,ioctl_addr[20:3]}) : cpu_mem_addr;
assign DDRAM_DIN=download_store ?
   ({48'd0,ioctl_dout} << (ioctl_addr[2:0]*8)) : cpu_mem_data;
assign DDRAM_BE=download_store ?
   (8'h03 << ioctl_addr[2:0]) : cpu_mem_be;
assign DDRAM_WE=download_store ? 1'b1 : (cpu_accept && cpu_mem_we);
assign DDRAM_RD=cpu_accept && !cpu_mem_we;

wire core_reset=!pll_locked | RESET | buttons[1] | status[0] | ioctl_download;
pace_firmware_cpu cpu (
    .clk(clk_sys),.reset(core_reset),.full_flash_loaded(full_flash_loaded),
    .mmio_policy(status[2:1]),
    .mem_req(cpu_mem_req),.mem_we(cpu_mem_we),
    .mem_addr(cpu_mem_addr),.mem_wdata(cpu_mem_data),.mem_be(cpu_mem_be),
    .mem_accept(cpu_accept),.mem_rvalid(cpu_rvalid),.mem_rdata(DDRAM_DOUT),
    .pc(pc),.instruction(inst),.retired(retired),
    .ram_writes(ram_writes),.last_ram_address(last_ram),
    .last_mmio_address(mmio_address),.last_mmio_value(mmio_value),
    .last_mmio_read(mmio_read),.mmio_writes(mmio_writes),
    .guessed_reads(guessed_reads),.halt_code(halt_code),
    .mips16(mips16),.reached_mips16(reach16)
);

// 720x576 PAL 2:1 interlace with 15.625 kHz H sync / 50 fields/s.
wire [9:0] x,y;
wire shown,hs,vs,field;
assign CLK_VIDEO=clk_sys;
pace_pal576i raster (
    .clk(clk_sys),.reset(!pll_locked),.ce_pixel(CE_PIXEL),
    .x(x),.y(y),.visible(shown),.hs(hs),.vs(vs),.field(field)
);
assign VGA_HS=hs;
assign VGA_VS=vs;
assign VGA_DE=shown;
assign VGA_F1=field;

wire [7:0] red,green,blue;
pace_boot_monitor monitor (
    .clk(clk_sys),.x(x),.y(y),.pc(pc),.instruction(inst),
    .retired(retired),.ram_writes(ram_writes),.last_ram_address(last_ram),
    .last_mmio_address(mmio_address),.last_mmio_value(mmio_value),
    .last_mmio_read(mmio_read),.mmio_writes(mmio_writes),
    .guessed_reads(guessed_reads),.halt_code(halt_code),
    .mips16(mips16),.full_flash_loaded(full_flash_loaded),
    .mmio_policy(status[2:1]),.r(red),.g(green),.b(blue)
);
assign VGA_R=shown ? red : 8'd0;
assign VGA_G=shown ? green : 8'd0;
assign VGA_B=shown ? blue : 8'd0;
assign LED_USER=halt_code==0 ? retired[21] : field;
endmodule
