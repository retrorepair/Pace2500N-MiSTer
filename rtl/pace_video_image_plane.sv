// SPDX-License-Identifier: GPL-3.0-only
// EMMA's RAM-backed PAL video plane. Native 3/3F -> provider8002156C ->
// 80009F60 programs B0004004/C (Y fields),4008/10 (interleaved U/V fields),
// 4014 (source size-1),4024 (output size-1), then800099B0 enables4000 bit0.
// These are the firmware's actual DMA7 pixels, not a host-provided picture.
// First supported profile: uncropped, unscaled720x576, packed unsignedYUV420.
module pace_video_image_plane(
 input wire clk,reset,bus_reset,hold,enable,
 input wire access,we,input wire [31:0] io_addr,io_wdata,
 output wire hit,output reg [31:0] io_rdata,
 output wire mem_req,output wire [28:0] mem_addr,output wire [7:0] mem_burst,
 input wire mem_accept,mem_rvalid,input wire [63:0] mem_rdata,
 input wire vclk,ce,visible,field,input wire [9:0] x,y,
 output reg [23:0] rgb=0,output reg valid=0,
 output reg [31:0] underruns=0
);
 reg [31:0] control=0;
 reg [23:0] y_even=0,y_odd=0,uv_even=0,uv_odd=0;
 reg [31:0] source_size=0,output_size=0,crop0=0,crop1=0,crop2=0;
 reg [31:0] scale0=0,scale1=0,scale2=0,source_extent=0;
 reg config_toggle=0;
 assign hit=io_addr[31:6]==26'h2c00100 && io_addr[5:0]<=6'h34 && io_addr[1:0]==0;
 always @* case(io_addr[5:0])
  'h00:io_rdata=control;'h04:io_rdata={8'd0,y_even};'h08:io_rdata={8'd0,uv_even};
  'h0c:io_rdata={8'd0,y_odd};'h10:io_rdata={8'd0,uv_odd};
  'h14:io_rdata=source_size;'h18:io_rdata=crop0;'h1c:io_rdata=crop1;'h20:io_rdata=crop2;
  'h24:io_rdata=output_size;'h28:io_rdata=scale0;'h2c:io_rdata=scale1;
  'h30:io_rdata=scale2;'h34:io_rdata=source_extent;default:io_rdata=0;
 endcase
 wire configured=enable && control[0] && !control[1] && source_size==32'h023f02cf &&
  output_size==32'h023f02cf && crop0==0 && crop1==0 && crop2==0 && source_extent==32'h024002d0 &&
  y_even!=0 && y_odd!=0 && uv_even!=0 && uv_odd!=0 &&
  {y_even[2:0],y_odd[2:0],uv_even[2:0],uv_odd[2:0]}==0;
 always @(posedge clk)begin
  if(reset)begin
   control<=0;y_even<=0;y_odd<=0;uv_even<=0;uv_odd<=0;source_size<=0;output_size<=0;
   crop0<=0;crop1<=0;crop2<=0;source_extent<=0;scale0<=0;scale1<=0;scale2<=0;config_toggle<=0;
  end else if(access && we && hit && !hold)case(io_addr[5:0])
   'h00:begin control<=io_wdata;config_toggle<=~config_toggle;end
   'h04:y_even<=io_wdata[23:0];'h08:uv_even<=io_wdata[23:0];
   'h0c:y_odd<=io_wdata[23:0];'h10:uv_odd<=io_wdata[23:0];
   'h14:source_size<=io_wdata;'h18:crop0<=io_wdata;'h1c:crop1<=io_wdata;'h20:crop2<=io_wdata;
   'h24:output_size<=io_wdata;'h28:scale0<=io_wdata;'h2c:scale1<=io_wdata;
   'h30:scale2<=io_wdata;'h34:source_extent<=io_wdata;
  endcase
 end

 // Two line banks. They are refetched two scan lines apart in interlaced output.
 (* ramstyle="M10K" *) reg [63:0] y_ram[0:191],uv_ram[0:191];
 reg [9:0] tag0=0,tag1=0;
 reg done0=0,done1=0,done_config0=0,done_config1=0;
 reg [2:0] done0_s=0,done1_s=0;
 reg [1:0] enabled_s=0,config_s=0,reset_s=3;
 reg [1:0] ready=0;reg [9:0] vtag0=0,vtag1=0;
 reg last_field=0,last_enabled=0,last_config=0;
 reg request_toggle=0;reg [9:0] requested_y=0;
 wire line_ok=ready[y[1]] && (y[1]?vtag1:vtag0)==y;
 reg [63:0] y_q=0,uv_q=0;reg [2:0] lane_q=0;
 reg show1=0,show2=0;
 reg signed [19:0] r2=0,g2=0,b2=0;
 wire [7:0] yy=y_q[lane_q*8+:8];
 wire [7:0] uu=uv_q[{lane_q[2:1],1'b0}*8+:8],vv=uv_q[{lane_q[2:1],1'b1}*8+:8];
 wire signed [9:0] yc=$signed({1'b0,yy})-10'sd16;
 wire signed [9:0] uc=$signed({1'b0,uu})-10'sd128,vc=$signed({1'b0,vv})-10'sd128;
 function automatic [7:0] clip(input signed [19:0] value);
  if(value<0)clip=0;else if(value>255)clip=255;else clip=value[7:0];
 endfunction
 wire [7:0] vword=(y[1]?8'd96:8'd0)+{1'b0,x[9:3]};
 always @(posedge vclk)begin
  reset_s<={reset_s[0],reset};enabled_s<={enabled_s[0],configured};config_s<={config_s[0],config_toggle};
  done0_s<={done0_s[1:0],done0};done1_s<={done1_s[1:0],done1};
  y_q<=y_ram[vword];uv_q<=uv_ram[vword];lane_q<=x[2:0];
  show1<=enabled_s[1] && visible && x<720 && y<576 && line_ok;
  r2<=298*yc+409*vc;g2<=298*yc-100*uc-208*vc;b2<=298*yc+516*uc;show2<=show1;
  rgb<={clip(r2>>>8),clip(g2>>>8),clip(b2>>>8)};valid<=show2;
  last_field<=field;last_enabled<=enabled_s[1];last_config<=config_s[1];
  if(reset_s[1] || !enabled_s[1] || config_s[1]!=last_config)ready<=0;
  else begin
   if(done0_s[2]!=done0_s[1] && done_config0==config_s[1])begin ready[0]<=1;vtag0<=tag0;end
   if(done1_s[2]!=done1_s[1] && done_config1==config_s[1])begin ready[1]<=1;vtag1<=tag1;end
  end
  if(enabled_s[1] && (field!=last_field || !last_enabled || config_s[1]!=last_config))begin
   ready<=0;requested_y<={9'd0,field};request_toggle<=~request_toggle;
  end else if(enabled_s[1] && ce && visible && x==0 && y<574)begin
   requested_y<=y+10'd2;request_toggle<=~request_toggle;
  end
 end

 // Eight-beat bursts bound shared-DDR overhead. Drain an accepted burst even
 // on disable/reconfiguration/CPU warm reset; its beats still belong to us.
 reg [2:0] req_s=0;reg pending=0;
 reg [9:0] pending_y=0,fetch_y=0;
 reg [1:0] state=0; //0 idle,1 request,2 data
 reg chroma=0,fetch_config=0,cancelled=0;
 reg [23:0] base_y=0,base_uv=0;
 reg [6:0] word_index=0;
 reg [3:0] beats_left=0;
 wire [7:0] burst_length=word_index<=82 ? 8'd8:8'd90-{1'b0,word_index};
 assign mem_req=state==1 && configured && !hold && !reset;
 assign mem_addr=29'h06000000+{8'd0,(chroma?base_uv[23:3]:base_y[23:3])}+{22'd0,word_index};
 assign mem_burst=burst_length;
 wire stale=cancelled || reset || !configured || fetch_config!=config_toggle;
 always @(posedge clk)begin
  req_s<={req_s[1:0],request_toggle};
  if(bus_reset)begin state<=0;beats_left<=0;pending<=0;cancelled<=0;underruns<=0;end
  else begin
   if(reset || !configured)begin
    pending<=0;cancelled<=1;
    if(state!=2)state<=0;
   end else if(req_s[2]!=req_s[1])begin
    pending<=1;pending_y<=requested_y;
    if(pending)underruns<=underruns+1'b1;
   end
   if(state==0 && pending && configured && !reset && !hold)begin
    pending<=0;fetch_y<=pending_y;chroma<=0;word_index<=0;
    base_y<=(pending_y[0]?y_odd:y_even)+(pending_y>>1)*24'd720;
    base_uv<=(pending_y[1]?uv_odd:uv_even)+(pending_y>>2)*24'd720;
    fetch_config<=config_toggle;cancelled<=0;state<=1;
   end
   if(mem_req && mem_accept)begin state<=2;beats_left<=burst_length[3:0];end
   if(state==2 && mem_rvalid)begin
    beats_left<=beats_left-1'b1;
    if(!stale)begin
     if(chroma)uv_ram[(fetch_y[1]?8'd96:8'd0)+{1'b0,word_index}]<=mem_rdata;
     else y_ram[(fetch_y[1]?8'd96:8'd0)+{1'b0,word_index}]<=mem_rdata;
    end
    word_index<=word_index+1'b1;
    if(beats_left==1)begin
     if(stale)state<=0;
     else if(word_index==89)begin
      if(!chroma)begin chroma<=1;word_index<=0;state<=1;end
      else begin
       if(fetch_y[1])begin tag1<=fetch_y;done_config1<=fetch_config;done1<=~done1;end
       else begin tag0<=fetch_y;done_config0<=fetch_config;done0<=~done0;end
       state<=0;
      end
     end else state<=1;
    end
   end
  end
 end
endmodule
