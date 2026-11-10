// SPDX-License-Identifier: GPL-3.0-only
// 625-line, 50-field/s 2:1 interlaced raster at the ITU-R BT.601 sample rate.
// 54 MHz video clock / 4 = 13.5 MHz samples, 864 samples per 64 us line
// (15,625 Hz), 720 active samples (53.33 us). The firmware's OSD fields are
// 720 pixels wide, so every guest pixel maps to exactly one output sample,
// as on the receiver's own PAL encoder.
// Horizontal blanking follows BT.601 625-line timing: 12 samples front porch,
// 64 samples sync (4.74 us), 68 samples back porch (12+64+68 = 144).
// 1,250 half-lines per 25 Hz frame; odd/even fields separated by 625
// half-lines. Equalising/serration pulses remain simplified, as in
// pace_pal576i.
module pace_pal576i601 (
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
    reg [8:0] half_x=0;        // 0..431, half-line sample counter
    reg [10:0] half_line=0;    // 0..1249, entire interlaced frame
    always @(posedge clk) begin
        if(reset)begin half_x<=0;half_line<=0;end
        else if(ce_pixel)begin
            if(half_x==9'd431)begin
                half_x<=0;
                half_line <= (half_line==11'd1249) ? 11'd0 : half_line+1'd1;
            end else half_x<=half_x+1'd1;
        end
    end
    assign field=(half_line>=11'd625);
    assign x = (half_line[0] ? 10'd432 : 10'd0)+{1'b0,half_x};
    wire [10:0] field_half = field ? half_line-11'd625 : half_line;
    wire [10:0] active_start = field ? 11'd41 : 11'd40;
    wire in_active_half = field_half>=active_start && field_half<active_start+11'd576;
    wire [10:0] active_half_index=field_half-active_start;
    wire [9:0] field_line=active_half_index[10:1];
    assign y={field_line[8:0],field};  // frame scan row: 0,2..574 / 1,3..575
    assign visible = in_active_half && x<10'd720;
    assign hs = ~((x>=10'd732) && (x<10'd796));
    assign vs = ~(field_half<11'd10);
endmodule
