// SPDX-License-Identifier: GPL-3.0-only
// Broadcast clock: rewrites the UTC_time of DVB TOT sections (table 0x73,
// PID 0x0014) in the replayed transport stream with the MiSTer RTC, and
// recomputes the section CRC32. The firmware then sets its own clock from
// the broadcast TOT, exactly as a receiver did from the live Sky signal.
//
// The MiSTer RTC (hps_io, MSM6242B layout, BCD) is maintained by MiSTer Linux,
// which synchronises it from the internet when a connection is present.
// Year handling: the two-digit RTC year maps to 2000-2099. A later OSD
// "time travel" year will replace rtc_year here.
//
// Only TOT sections that start in a packet with payload-only adaptation
// control, pointer_field 0, and that end inside the same packet are
// rewritten (the replay fixture's TOT is ~29 bytes). Anything else passes
// through unchanged, so the demux still validates the original CRC.
module pace_tot_clock (
 input wire clk,reset,enable,
 input wire [64:0] rtc,           // hps_io RTC: [47:40] yy,[39:32] mm,[31:24] dd,[23:16] hh,[15:8] mi,[7:0] ss (BCD)
 input wire in_valid,output wire in_ready,input wire [7:0] in_data,
 output wire out_valid,input wire out_ready,output wire [7:0] out_data,
 output reg [31:0] rewritten=0
);
 assign out_valid=in_valid;
 assign in_ready=out_ready;
 wire step=in_valid && out_ready;
 // ---- RTC -> DVB UTC_time (MJD + BCD hh mm ss), registered once per change.
 function automatic [6:0] bcd2bin(input [7:0] b);bcd2bin=b[7:4]*7'd10+b[3:0];endfunction
 reg [15:0] mjd=0;reg [23:0] hms=0;
 reg [6:0] yy=0,mo=1,dd=1;
 reg [8:0] month_days=0;
 always @* begin
  case(mo)
   1:month_days=0;   2:month_days=31;  3:month_days=59;  4:month_days=90;
   5:month_days=120; 6:month_days=151; 7:month_days=181; 8:month_days=212;
   9:month_days=243; 10:month_days=273;11:month_days=304;12:month_days=334;
   default:month_days=0;
  endcase
 end
 always @(posedge clk)begin
  yy<=bcd2bin(rtc[47:40]);mo<=bcd2bin(rtc[39:32]);dd<=bcd2bin(rtc[31:24]);
  hms<=rtc[23:0];
  // MJD(2000-01-01)=51544; leap years 2000..2099 are those divisible by 4.
  mjd<=16'd51544+16'd365*yy+((yy+16'd3)>>2)+month_days+((yy[1:0]==0 && mo>2) ? 16'd1:16'd0)+dd-16'd1;
 end
 wire rtc_ok=mo>=1 && mo<=12 && dd>=1 && dd<=31;
 // ---- Packet / section tracking.
 reg [7:0] pkt_pos=0;
 reg [12:0] pid=0;reg pusi=0,payload_only=0;
 reg active=0;              // rewriting the TOT that starts in this packet
 reg [11:0] sec_pos=0,sec_total=0;
 reg [47:0] utc_shadow=0;   // latched at section start so all 5 bytes agree
 reg [31:0] crc=32'hffffffff;
 function automatic [31:0] crc_byte(input [31:0] c,input [7:0] d);
  integer i;reg [31:0] r;
  begin r=c^{d,24'd0};for(i=0;i<8;i=i+1)r=r[31] ? (r<<1)^32'h04c11db7:(r<<1);crc_byte=r;end
 endfunction
 wire in_section=active && pkt_pos>=8'd5;
 wire [7:0] utc_byte=sec_pos==3 ? utc_shadow[39:32]:sec_pos==4 ? utc_shadow[31:24]:sec_pos==5 ? utc_shadow[23:16]:
                     sec_pos==6 ? utc_shadow[15:8]:utc_shadow[7:0];
 wire crc_zone=in_section && sec_total>=12'd12 && sec_pos>=sec_total-12'd4 && sec_pos<sec_total;
 wire [1:0] crc_index=sec_pos-(sec_total-12'd4);
 wire [7:0] crc_out=crc_index==0 ? crc[31:24]:crc_index==1 ? crc[23:16]:crc_index==2 ? crc[15:8]:crc[7:0];
 assign out_data=!in_section ? in_data :
                 (sec_pos>=3 && sec_pos<=7 && sec_total>=12'd12) ? utc_byte :
                 crc_zone ? crc_out : in_data;
 always @(posedge clk)begin
  if(reset)begin pkt_pos<=0;active<=0;rewritten<=0;end
  else if(step)begin
   pkt_pos<=pkt_pos==8'd187 ? 8'd0:pkt_pos+8'd1;
   case(pkt_pos)
    1:begin pusi<=in_data[6];pid[12:8]<=in_data[4:0];end
    2:pid[7:0]<=in_data;
    3:payload_only<=in_data[5:4]==2'b01;
    4:begin
     // pointer_field 0 and TOT PID with a section start in this packet
     active<=enable && rtc_ok && pusi && payload_only && pid==13'h0014 && in_data==8'd0;
     sec_pos<=0;sec_total<=0;crc<=32'hffffffff;utc_shadow<={8'd0,mjd,hms};
    end
    default:begin end
   endcase
   if(in_section)begin
    sec_pos<=sec_pos+12'd1;
    if(sec_pos==0 && in_data!=8'h73)active<=0;
    if(sec_pos==1)sec_total<={in_data[3:0],8'd0};
    if(sec_pos==2)begin
     sec_total<=sec_total+{4'd0,in_data}+12'd3;
     // the whole section must end inside this packet
     if(12'd5+sec_total+{4'd0,in_data}+12'd3>12'd188)active<=0;
    end
    if(sec_pos<3 || (sec_total!=0 && sec_pos<sec_total-12'd4))crc<=crc_byte(crc,out_data);
    if(sec_total!=0 && sec_pos==sec_total-12'd1)begin active<=0;rewritten<=rewritten+1'b1;end
   end
   if(pkt_pos==8'd187)active<=0;
  end
 end
endmodule
