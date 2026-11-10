// SPDX-License-Identifier: GPL-3.0-only
// DMA scanout of the guest's real 8bpp interlaced OSD display list and CLUT,
// one guest pixel per BT.601 13.5 MHz sample (720 active samples per line).
// Replaces pace_guide_video's 640-sample nearest sampling, which dropped
// every ninth pixel column and visibly distorted text.
//
// Two clock domains: clk (core/DDR) fetches the display list, CLUT and lines;
// vclk (54 MHz video) runs the raster and reads the dual-clock line/palette
// RAMs. Crossings use toggle handshakes; each multi-bit value is written
// before its toggle and then held stable for at least one scan line.
module pace_guide_video601 (
 input wire clk,reset,hold,
 input wire [31:0] osd_root,
 output reg [7:0] error=0,
 output reg [31:0] frames=0,underruns=0,
 output reg mem_req=0,
 output reg [28:0] mem_addr=0,
 input wire mem_accept,mem_rvalid,
 input wire [63:0] mem_rdata,
 input wire vclk,
 input wire [9:0] x,y,
 input wire ce,visible,hs,vs,field,
 output reg out_ce=0,out_visible=0,out_hs=1,out_vs=1,out_field=0,
 output reg [23:0] rgb=0,
 // 1 = no OSD pixel here: CLUT entry 0x0000 (the value the firmware uses for
 // its cleared plane in live viewing), or no OSD line available.
 output reg key=1
);
 localparam IDLE=0,REQUEST=1,WAIT_DATA=2,PALETTE_WRITE=3;
 // ---------------- shared memories (write clk, read vclk) ----------------
 (* ramstyle="M10K" *) reg [63:0] line_ram[0:179];
 (* ramstyle="M10K" *) reg [95:0] palette_ram[0:63];  // 4 x RGB888 per word
 reg [3:0] key_ram[0:63];                               // 4 x transparent flag per word
 reg [3:0] key_q=0;
 // ---------------- video domain ----------------
 reg [1:0] vreset_s=2'b11;
 wire vreset=vreset_s[1];
 reg vlast_field=0,vfield_toggle=0,vfield_value=0;
 reg vreq_toggle=0,vunder_toggle=0;
 reg [9:0] vreq_line=0;
 reg [1:0] vready=0;
 reg [9:0] vtag0=0,vtag1=0;
 reg [2:0] done0_s=0,done1_s=0;
 reg [1:0] vpal_s=0;
 // core-domain sources read by the video domain (held stable, see above)
 reg done0_toggle=0,done1_toggle=0,palette_valid=0;
 reg [9:0] line_tag0=0,line_tag1=0;
 wire [7:0] line_word=(y[1]?8'd90:8'd0)+{1'b0,x[9:3]};
 wire line_ok=vready[y[1]] && (y[1]?vtag1:vtag0)==y;
 reg [63:0] line_q=0;reg [2:0] lane_q=0;reg show1=0;
 reg [95:0] pal_q=0;reg [1:0] sel2=0;reg show2=0;
 reg [4:0] ctrl1=5'b01100,ctrl2=5'b01100; // {ce,visible,hs,vs,field}
 wire [7:0] pixel_index=line_q[lane_q*8+:8];
 always @(posedge vclk)begin
  vreset_s<={vreset_s[0],reset};
  done0_s<={done0_s[1:0],done0_toggle};done1_s<={done1_s[1:0],done1_toggle};
  vpal_s<={vpal_s[0],palette_valid};
  // Pipeline: line RAM -> palette RAM -> RGB, controls delayed to match.
  line_q<=line_ram[line_word];lane_q<=x[2:0];show1<=vpal_s[1] && line_ok;
  ctrl1<={ce,visible,hs,vs,field};
  pal_q<=palette_ram[pixel_index[7:2]];key_q<=key_ram[pixel_index[7:2]];sel2<=pixel_index[1:0];show2<=show1;ctrl2<=ctrl1;
  rgb<=show2?pal_q[sel2*24+:24]:24'd0;key<=show2 ? key_q[sel2] : 1'b1;
  {out_ce,out_visible,out_hs,out_vs,out_field}<=ctrl2;
  if(vreset)begin
   vlast_field<=field;vready<=0;
  end else begin
   vlast_field<=field;
   if(field!=vlast_field)begin vfield_value<=field;vfield_toggle<=~vfield_toggle;vready<=0;end
   if(ce && visible && x==0 && y<574)begin vreq_line<=y+10'd2;vreq_toggle<=~vreq_toggle;end
   if(ce && visible && x==0 && !line_ok)vunder_toggle<=~vunder_toggle;
   if(done0_s[2]!=done0_s[1])begin vready[0]<=1;vtag0<=line_tag0;end
   if(done1_s[2]!=done1_s[1])begin vready[1]<=1;vtag1<=line_tag1;end
  end
 end
 always @(posedge vclk)begin end
 // ---------------- core domain ----------------
 reg [1:0] state=0;
 reg [1:0] phase=0; //0 geometry/CLUT,1 fields,2 palette,3 line
 reg [23:0] descriptor=0,clut=0,even_base=0,odd_base=0;
 reg [6:0] read_index=0;
 reg initial_frame=1,header_pending=0,line_pending=0;
 reg [9:0] requested_line=0,fetch_line=0;
 reg [63:0] palette_data=0;
 reg [2:0] req_s=0,field_s=0,under_s=0;
 wire req_event=req_s[2]!=req_s[1],field_event=field_s[2]!=field_s[1],under_event=under_s[2]!=under_s[1];
 function automatic[31:0] be_word(input[31:0] w);be_word={w[7:0],w[15:8],w[23:16],w[31:24]};endfunction
 function automatic[7:0] clamp(input integer value);
  begin if(value<0)clamp=0;else if(value>255)clamp=255;else clamp=value[7:0];end
 endfunction
 function automatic[23:0] colour(input[15:0] v);
  reg signed[8:0] yc,cb,cr;
  reg signed[18:0] yy,rv,gv,bv;
  begin
   yc=$signed({1'b0,v[13:8],2'b00})-9'sd16;
   cb=$signed({1'b0,v[7:4],4'b0000})-9'sd128;cr=$signed({1'b0,v[3:0],4'b0000})-9'sd128;
   yy=yc*19'sd298;rv=yy+19'sd409*cr;gv=yy-19'sd100*cb-19'sd208*cr;bv=yy+19'sd516*cb;
   colour={clamp(rv>>>8),clamp(gv>>>8),clamp(bv>>>8)};
  end
 endfunction
 wire [31:0] low_word=be_word(mem_rdata[31:0]),high_word=be_word(mem_rdata[63:32]);
 wire [31:0] palette_low=be_word(palette_data[31:0]),palette_high=be_word(palette_data[63:32]);
 wire [31:0] line_address=(fetch_line[0]?{8'd0,odd_base}:{8'd0,even_base})+(fetch_line>>1)*720;
 // Memory write ports (core clock).
 reg line_we=0,palette_we=0;reg [7:0] line_waddr=0;reg [63:0] line_wdata=0;
 reg [5:0] palette_waddr=0;reg [95:0] palette_wdata=0;reg [3:0] key_wdata=0;
 always @(posedge clk)begin
  if(line_we)line_ram[line_waddr]<=line_wdata;
  if(palette_we)begin palette_ram[palette_waddr]<=palette_wdata;key_ram[palette_waddr]<=key_wdata;end
 end
 always @(posedge clk)begin
  req_s<={req_s[1:0],vreq_toggle};field_s<={field_s[1:0],vfield_toggle};under_s<={under_s[1:0],vunder_toggle};
  line_we<=0;palette_we<=0;
  if(reset)begin
   state<=IDLE;mem_req<=0;initial_frame<=1;header_pending<=0;line_pending<=0;
   palette_valid<=0;error<=0;frames<=0;underruns<=0;
  end else if(!hold && error==0)begin
   if(under_event)underruns<=underruns+1'b1;
   if(initial_frame || field_event)begin
    initial_frame<=0;
    if(osd_root[24] && osd_root[23:0]!=0)begin
     descriptor<=osd_root[23:0];header_pending<=1;requested_line<={9'd0,vfield_value};frames<=frames+1'b1;
    end
   end
   // Fetch the following line while this line is displayed, into the other buffer.
   if(req_event)begin requested_line<=vreq_line;line_pending<=1;end
   case(state)
    IDLE:begin
     if(header_pending)begin header_pending<=0;phase<=0;read_index<=0;state<=REQUEST;end
     else if(line_pending && palette_valid)begin
      line_pending<=0;fetch_line<=requested_line;read_index<=0;phase<=3;state<=REQUEST;
     end
    end
    REQUEST:begin
     mem_req<=1;
     case(phase)
      0:mem_addr<=29'h06000000+(({8'd0,descriptor}+8)>>3);
      1:mem_addr<=29'h06000000+(({8'd0,descriptor}+16)>>3);
      2:mem_addr<=29'h06000000+{8'd0,clut[23:3]}+read_index;
      3:mem_addr<=29'h06000000+(line_address>>3)+read_index;
     endcase
     if(mem_req && mem_accept)begin mem_req<=0;state<=WAIT_DATA;end
    end
    WAIT_DATA:if(mem_rvalid)begin
     case(phase)
      0:begin
       if(descriptor[2:0]!=0 || low_word!=32'h023f02cf || high_word[2:0]!=0)error<=8'hc0;
       else begin clut<=high_word[23:0];phase<=1;state<=REQUEST;end
      end
      1:begin
       if(low_word[26:25]!=3 || low_word[2:0]!=0 || high_word[2:0]!=0)error<=8'hc1;
       else begin even_base<=low_word[23:0];odd_base<=high_word[23:0];phase<=2;read_index<=0;state<=REQUEST;end
      end
      2:begin
       palette_data<=mem_rdata;state<=PALETTE_WRITE;
      end
      3:begin
       line_we<=1;line_waddr<=(fetch_line[1]?8'd90:8'd0)+{1'b0,read_index};line_wdata<=mem_rdata;
       if(read_index==89)begin
        // Tag is written with its toggle and held until this bank is refetched
        // two scan lines later, so the video domain samples a stable value.
        if(fetch_line[1])begin line_tag1<=fetch_line;done1_toggle<=~done1_toggle;end
        else begin line_tag0<=fetch_line;done0_toggle<=~done0_toggle;end
        state<=IDLE;
       end else begin read_index<=read_index+1'b1;state<=REQUEST;end
      end
     endcase
    end
    PALETTE_WRITE:begin
     palette_we<=1;palette_waddr<=read_index[5:0];
     palette_wdata<={colour(palette_high[15:0]),colour(palette_high[31:16]),
                     colour(palette_low[15:0]),colour(palette_low[31:16])};
     key_wdata<={palette_high[15:0]==0,palette_high[31:16]==0,palette_low[15:0]==0,palette_low[31:16]==0};
     if(read_index==63)begin palette_valid<=1;phase<=3;fetch_line<=requested_line;line_pending<=0;read_index<=0;state<=REQUEST;end
     else begin read_index<=read_index+1'b1;state<=REQUEST;end
    end
    default:error<=8'hcf;
   endcase
  end
 end
endmodule
