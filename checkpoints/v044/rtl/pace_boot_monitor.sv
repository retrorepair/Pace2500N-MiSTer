// SPDX-License-Identifier: GPL-3.0-only
// Minimal LIVE 576i boot monitor. No ROM hex viewer/extra ROM read ports.
module pace_boot_monitor (
    input wire clk,
    input wire [9:0] x, y,
    input wire [31:0] pc,instruction,retired,ram_writes,last_ram_address,
    input wire [31:0] last_mmio_address,last_mmio_value,last_mmio_read,
    input wire [31:0] mmio_writes,guessed_reads,
    input wire [7:0] halt_code,
    input wire mips16,full_flash_loaded,
    input wire [1:0] mmio_policy,
    output reg [7:0] r,g,b
);
    (* ramstyle = "M10K" *) reg [7:0] fontrom[0:1023];
    (* ramstyle = "M10K" *) reg [7:0] mainrom[0:2431];
    initial begin
        $readmemh("rom/font8x8.hex", fontrom);
        $readmemh("rom/monitor.hex",mainrom);
    end
    wire in_rect = x>=10'd16 && x<10'd624 && y>=10'd32 && y<10'd544;
    wire [9:0] lx = x - 10'd16;
    wire [9:0] ly = y - 10'd32;
    wire [6:0] col = in_rect ? lx[9:3] : 7'd0;
    wire [4:0] row = in_rect ? ly[8:4] : 5'd0;
    wire [11:0] tile_addr=({7'd0,row}<<6)+({7'd0,row}<<3)+
                          ({7'd0,row}<<2)+{5'd0,col};
    reg [7:0] main_char;
    always @(posedge clk) main_char<=mainrom[tile_addr];
    function automatic [7:0] hchar(input [3:0] n);
        hchar = (n<10) ? (8'h30+n) : (8'h41+n-4'd10);
    endfunction
    function automatic [7:0] hdigit(input [31:0] v,input [2:0] dig);
        hdigit=hchar((v>>(28-({29'd0,dig}<<2))) & 4'hf);
    endfunction
    reg [31:0] chosen;
    always @* begin
        case(row)
          7:chosen=pc;
          8:chosen=instruction;
          9:chosen=retired;
          10:chosen=ram_writes;
          11:chosen=last_ram_address;
          12:chosen=last_mmio_address;
          13:chosen=last_mmio_value;
          14:chosen=mmio_writes;
          15:chosen=last_mmio_read;
          16:chosen=guessed_reads;
          17:chosen={31'd0,mips16};
          18:chosen={24'd0,halt_code};
          19:chosen={31'd0,full_flash_loaded};
          20:chosen={30'd0,mmio_policy};
          default:chosen=0;
        endcase
    end
    reg [7:0] chr;
    always @* begin
        chr=main_char;
        if(row>=7 && row<=20 && col>=35 && col<=42)
            chr=hdigit(chosen, col-7'd35);
    end
    reg [7:0] font_bits;
    always @(posedge clk) font_bits<=fontrom[{chr[6:0],ly[3:1]}];
    wire lit=font_bits[7-lx[2:0]];
    always @* begin
        if(!in_rect)begin r=8'h00;g=8'h05;b=8'h15;end
        else if(row<=1)begin
            r=lit?8'hff:8'h08;g=lit?8'hff:8'h22;b=lit?8'hff:8'h6a;
        end else if(row==22 && halt_code!=0)begin
            r=lit?8'hff:8'h5a;g=lit?8'hff:8'h12;b=lit?8'hff:8'h28;
        end else begin
            r=lit?8'hdc:8'h03;g=lit?8'he9:8'h0f;b=lit?8'hff:8'h33;
        end
    end
endmodule
