// SPDX-License-Identifier: GPL-3.0-only
// 625-line, 50-field/s 2:1 interlaced RGB generator for PAL CRT output.
// 50 MHz clock / 4 = 12.5 MHz pixels, 800 pixels per line -> 15,625 Hz.
// 1,250 half-lines per 25 Hz frame; odd/even fields separated by 625
// half-lines, providing the essential half-line phase displacement.
// 640x576 active samples (288 scan lines per field); 640 * 80 ns = 51.2 us.
// The precise analogue sync equalising/serration envelope is simplified;
// check field lock on real CRT and refine against ITU-R BT.470 if needed.
module pace_pal576i (
    input  wire        clk,
    input  wire        reset,
    output wire        ce_pixel,
    output wire [9:0]  x,
    output wire [9:0]  y,
    output wire        visible,
    output wire        hs,
    output wire        vs,
    output wire        field
);
    reg [1:0] divider=0;
    always @(posedge clk) divider <= divider+2'd1;
    assign ce_pixel=(divider==2'd3);
    reg [8:0] half_x=0;        // 0..399, half-line pixel clock
    reg [10:0] half_line=0;    // 0..1249, entire interlaced frame
    always @(posedge clk) begin
        if(reset)begin half_x<=0;half_line<=0;end
        else if(ce_pixel)begin
            if(half_x==9'd399)begin
                half_x<=0;
                half_line <= (half_line==11'd1249) ? 11'd0 : half_line+1'd1;
            end else half_x<=half_x+1'd1;
        end
    end
    assign field=(half_line>=11'd625);
    // Half-line parity gives an exact 400-pixel displacement between fields.
    assign x = (half_line[0] ? 10'd400 : 10'd0)+{1'b0,half_x};
    wire [10:0] field_half = field ? half_line-11'd625 : half_line;
    // The odd field's visible start is a half-line later. Both displayed
    // scan lines begin at x=0; the field sync starts half a line offset.
    wire [10:0] active_start = field ? 11'd41 : 11'd40;
    wire in_active_half = field_half>=active_start && field_half<active_start+11'd576;
    wire [10:0] active_half_index=field_half-active_start;
    wire [9:0] field_line=active_half_index[10:1];
    assign y={field_line[8:0],field};  // actual frame scan row: 0,2..574 / 1,3..575
    assign visible = in_active_half && x<10'd640;
    // CRT porches: 640 active + 20 front + 60 sync + 80 back = 800.
    assign hs = ~((x>=10'd660) && (x<10'd720));
    // Vertical pulse extends across 5 full lines at each field transition.
    assign vs = ~(field_half<11'd10);
endmodule
