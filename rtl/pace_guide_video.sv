// SPDX-License-Identifier: GPL-3.0-only
// DMA scanout of the guest's real8bpp interlaced OSD display list and CLUT.
// PAL active640samples nearest-samples the firmware's720 indexed pixels.
module pace_guide_video (
 input wire clk,reset,hold,
 input wire [31:0] osd_root,
 input wire [9:0] x,y,
 input wire ce,visible,hs,vs,field,
 output reg out_ce=0,out_visible=0,out_hs=1,out_vs=1,out_field=0,
 output reg [23:0] rgb=0,
 output reg [7:0] error=0,
 output reg [31:0] frames=0,underruns=0,
 output reg mem_req=0,
 output reg [28:0] mem_addr=0,
 input wire mem_accept,mem_rvalid,
 input wire [63:0] mem_rdata
);
 localparam IDLE=0,REQUEST=1,WAIT_DATA=2,PALETTE_WRITE=3;
 reg [1:0] state=0;
 reg [1:0] phase=0; //0 geometry/CLUT,1 fields,2 palette,3 line
 reg [23:0] descriptor=0,clut=0,even_base=0,odd_base=0;
 reg [6:0] read_index=0;
 reg last_field=0,initial_frame=1,header_pending=0,line_pending=0,palette_valid=0;
 reg [9:0] requested_line=0,fetch_line=0;
 reg [1:0] ready=0;
 reg [9:0] line_tag[0:1];
 reg [63:0] line_ram[0:179];
 reg [23:0] palette[0:255];
 reg [63:0] palette_data=0;
 wire [9:0] native_x=x+(x>>3);
 wire [7:0] line_word=(y[1]?8'd90:8'd0)+{1'b0,native_x[9:3]};
 reg [63:0] line_q=0;reg [2:0] lane_q=0;
 reg ce_q=0,visible_q=0,hs_q=1,vs_q=1,field_q=0;
 reg show_q=0;
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
 always @(posedge clk)begin
  // Registered dual-port line and palette memories, with matching sync delay.
  line_q<=line_ram[line_word];lane_q<=native_x[2:0];
  show_q<=palette_valid && ready[y[1]] && line_tag[y[1]]==y;
  rgb<=show_q?palette[line_q[lane_q*8+:8]]:24'd0;
  ce_q<=ce;visible_q<=visible;hs_q<=hs;vs_q<=vs;field_q<=field;
  out_ce<=ce_q;out_visible<=visible_q;out_hs<=hs_q;out_vs<=vs_q;out_field<=field_q;
  if(reset)begin
   state<=IDLE;mem_req<=0;last_field<=field;initial_frame<=1;header_pending<=0;line_pending<=0;
   palette_valid<=0;ready<=0;error<=0;frames<=0;underruns<=0;
  end else if(!hold && error==0)begin
   last_field<=field;
   if(initial_frame || field!=last_field)begin
    initial_frame<=0;
    if(osd_root[24] && osd_root[23:0]!=0)begin
     descriptor<=osd_root[23:0];header_pending<=1;requested_line<={9'd0,field};ready<=0;frames<=frames+1'b1;
    end
   end
   // Fetch the following line while this line is displayed, into the other
   // buffer. Waiting for the final active pixel leaves only a short porch.
   if(ce && visible && x==0 && y<574)begin requested_line<=y+2;line_pending<=1;end
   if(ce && visible && x==0 && (!ready[y[1]] || line_tag[y[1]]!=y))underruns<=underruns+1'b1;
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
       line_ram[(fetch_line[1]?8'd90:8'd0)+{1'b0,read_index}]<=mem_rdata;
       if(read_index==89)begin ready[fetch_line[1]]<=1;line_tag[fetch_line[1]]<=fetch_line;state<=IDLE;end
       else begin read_index<=read_index+1'b1;state<=REQUEST;end
      end
     endcase
    end
    PALETTE_WRITE:begin
     palette[{read_index[5:0],2'b00}]<=colour(palette_low[31:16]);
     palette[{read_index[5:0],2'b01}]<=colour(palette_low[15:0]);
     palette[{read_index[5:0],2'b10}]<=colour(palette_high[31:16]);
     palette[{read_index[5:0],2'b11}]<=colour(palette_high[15:0]);
     if(read_index==63)begin palette_valid<=1;phase<=3;fetch_line<=requested_line;line_pending<=0;read_index<=0;state<=REQUEST;end
     else begin read_index<=read_index+1'b1;state<=REQUEST;end
    end
    default:error<=8'hcf;
   endcase
  end
 end
endmodule
