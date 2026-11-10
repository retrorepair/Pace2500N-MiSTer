// SPDX-License-Identifier: GPL-3.0-only
// FPGA implementation of the disclosed software diagnostic's runtime profile.
// Resume-only, no RF, diagnostic EEPROM/unknown-MMIO-zero/transport ACK policy.
module pace_guide_peripherals #(
 parameter [31:0] TIMER_COUNTS_PER_INSTRUCTION=1
) (
 input wire clk,reset,hold,
 input wire [31:0] retired,
 input wire io_req,io_we,
 input wire [31:0] io_addr,io_wdata,
 input wire [1:0] io_size,
 output reg [31:0] io_rdata,
 output wire io_ready,io_irq,
 input wire key_valid,key_pressed,
 input wire [7:0] key_code,
 output reg gpu_start=0,
 output wire [31:0] gpu_descriptor,osd_root,
 input wire gpu_done,transport_irq,transport_lock,
 output reg [7:0] model_halt=0,
 output reg [31:0] serial_frames=0,key_frames=0,timer_acks=0,gpu_acks=0,
 output reg [7:0] last_key=0
);
 `include "rtl/pace_checkpoint_csr.vh"
 reg [31:0] seed[0:127],csr[0:127];
 initial $readmemh("rom/checkpoint_csr.hex",seed);
 function automatic [31:0] regval(input[31:0] a);regval=csr[csr_index(a)];endfunction
 reg [31:0] last_retired=0;
 wire tick=retired!=last_retired;
 reg [31:0] timer_remaining=740656;
 reg timer_pending=0,gpu_pending=0;
 reg [13:0] clock_delay=0;
 reg clock_waiting=0;
 reg [7:0] serial_rx=0;
 reg [7:0] tx_body[0:15];reg [4:0] tx_count=0;reg tx_escape=0;
 reg ack_pending=0;reg [47:0] ack_body=0;reg [2:0] ack_len=0;
 reg [7:0] key_queue[0:15];reg [3:0] key_write=0,key_read=0;
 reg wire_active=0,wire_escape=0;reg [47:0] wire_body=0;
 reg [2:0] wire_len=0,wire_pos=0;
 wire [7:0] wire_raw=wire_body >> ((5-wire_pos)*8);
 wire [7:0] wire_byte=!wire_active?8'd0 : wire_pos==wire_len?8'd0 :
          (!wire_escape && (wire_raw==0 || wire_raw==8'h1b))?8'h1b:wire_raw;
 reg [7:0] i2c_address=0;
 reg i2c_address_valid=0,i2c_start=0,i2c_receive=0,i2c_first_payload=0;
 reg [6:0] i2c_delay=0,serial0_delay=0;
 reg [2:0] lsi_group=7;reg [12:0] lsi_apr=29;
 (* ramstyle="M10K" *) reg [7:0] lsi4[0:127];initial $readmemh("rom/checkpoint_lsi4.hex",lsi4);
 (* ramstyle="M10K" *) reg [7:0] eeprom[0:65535];initial $readmemh("rom/checkpoint_eeprom.hex",eeprom);
 reg [7:0] lsi4_q=0,eeprom_q=0;
 reg [15:0] ee_pointer=14090;
 reg [1:0] ee_address_count=0;
 reg [7:0] ee_address_high=0;
 reg [7:0] ee_pending_data[0:255];reg [15:0] ee_pending_addr[0:255];
 reg [8:0] ee_pending_count=0,ee_commit_count=0,ee_commit_index=0;
 reg [7:0] uart[0:7];
 wire i2c_ack=i2c_address_valid && (i2c_address==8'hca || i2c_address==0 ||
       i2c_address[7:1]==7'h0c || i2c_address[7:1]==7'h50);
 wire [31:0] irq_status=(timer_pending && (regval(32'hb000d0c0)&1)!=0?32'h40:32'd0) |
       ((regval(32'hb2009020)&regval(32'hb2009030)&1)!=0?32'h2000:32'd0) |
       ((regval(32'hb2006050)&regval(32'hb2006060)&1)!=0?32'h200000:32'd0) |
       ((regval(32'hb2002060)&regval(32'hb2002070))!=0?32'h10000:32'd0) |
       (gpu_pending?32'd2:32'd0) | (transport_irq?32'h01000000:32'd0);
 assign io_irq=(irq_status&regval(32'hb0000040))!=0;
 assign io_ready=io_req && ee_commit_count==0 && model_halt==0;
 assign gpu_descriptor=regval(32'hb0009100);
 assign osd_root=regval(32'hb0004200);
 integer n;
 // Explicit registered read ports keep the EEPROM in block RAM. Addresses
 // settle many core clocks before the64-instruction I2C completion deadline.
 always @(posedge clk)begin
  eeprom_q<=eeprom[ee_pointer];
  lsi4_q<=lsi4[lsi_apr[6:0]];
  if(!reset && !hold && ee_commit_count!=0)
   eeprom[ee_pending_addr[ee_commit_index[7:0]]]<=ee_pending_data[ee_commit_index[7:0]];
 end
 always @* begin
   io_rdata=regval(io_addr);
   case(io_addr)
    32'hb0000030:io_rdata=irq_status;
    32'hb000d0d0:io_rdata={31'd0,timer_pending};
    32'hb2009010:io_rdata={24'd0,serial_rx};
    32'hb0009120,32'hb0009122:io_rdata=gpu_pending?32'h1000:32'd0;
    32'hb0009140,32'hb0009142:io_rdata=0;
    32'hb0006040:io_rdata=0;
    32'hb2001000,32'hb2001003:io_rdata=0;
    32'hb2001020,32'hb2001023:io_rdata=1;
    32'hb2001050,32'hb2001053:io_rdata=32'h60;
    default:begin end
   endcase
   if(io_addr>=32'hb4080000 && io_addr<32'hb4080008)begin
      case(io_addr[2:0]^3'b011)
       0:io_rdata=uart[3][7]?32'd4:32'd0;
       1:io_rdata=uart[3][7]?32'd0:{24'd0,uart[1]};
       2:io_rdata=1;
       5:io_rdata=32'h60;
       default:io_rdata={24'd0,uart[io_addr[2:0]^3'b011]};
      endcase
   end
   if(io_size==0)io_rdata=io_rdata&32'hff;
   else if(io_size==1)io_rdata=io_rdata&32'hffff;
 end
 always @(posedge clk)begin
  gpu_start<=0;
  if(reset)begin
   for(n=0;n<128;n=n+1)csr[n]<=seed[n];
   for(n=0;n<8;n=n+1)uart[n]<=0;
   uart[3]<=3;
   last_retired<=retired;timer_remaining<=740656;timer_pending<=0;gpu_pending<=0;
   clock_waiting<=0;serial_rx<=0;clock_delay<=0;tx_count<=0;tx_escape<=0;
   ack_pending<=0;key_write<=0;key_read<=0;wire_active<=0;wire_escape<=0;
   i2c_delay<=0;serial0_delay<=0;i2c_address_valid<=0;i2c_start<=0;
   lsi_group<=7;lsi_apr<=29;ee_pointer<=14090;ee_address_count<=0;
   ee_pending_count<=0;ee_commit_count<=0;ee_commit_index<=0;
   model_halt<=0;serial_frames<=0;key_frames<=0;timer_acks<=0;gpu_acks<=0;last_key<=0;
  end else if(hold)last_retired<=retired;
  else begin
   last_retired<=retired;
   if(key_valid && key_pressed)begin
     if(key_write+4'd1==key_read)model_halt<=8'he0;
     else begin key_queue[key_write]<=key_code;key_write<=key_write+1'b1;last_key<=key_code;end
   end
   // Only select a new message between complete escaped frames.
   if(!wire_active)begin
    if(ack_pending)begin
     wire_body<=ack_body;wire_len<=ack_len;ack_pending<=0;wire_pos<=0;wire_escape<=0;wire_active<=1;
    end else if(key_read!=key_write)begin
     wire_body<={8'h05,8'h00,8'h02,8'h00,4'd0,key_queue[key_read][7:4],key_queue[key_read][3:0],4'd0};
     wire_len<=6;wire_pos<=0;wire_escape<=0;wire_active<=1;key_read<=key_read+1'b1;key_frames<=key_frames+1'b1;
    end
   end
   if(!clock_waiting && wire_active && (regval(32'hb200a000)&1)!=0 && (regval(32'hb2009020)&1)==0)begin
     clock_waiting<=1;clock_delay<=8192;
   end
   if(ee_commit_count!=0)begin
    ee_commit_index<=ee_commit_index+1'b1;ee_commit_count<=ee_commit_count-1'b1;
   end
   if(tick)begin
    // Instruction-domain timebase (platform workaround, FPGA CPU speed).
    // The NEC part runs ~81M instructions/s; this FPGA CPU retires ~2.5M/s,
    // so guest time is defined by retired instructions, not wall clock.
    // Firmware evidence: EMMA timer reload 810000 and CP0 Compare reload
    // 202500 (exactly 810000/4) are both the Nucleus tick, i.e. an 81 MHz
    // timer clock (3 x 27 MHz) and 10 ms tick. NEC rates the uPD6103x CPU at
    // 66-100 MIPS, so one timer count per retired instruction (81 MIPS) is
    // used. The previous 32 counts/instruction gave the firmware ~25K
    // instructions per tick instead of ~810K, starving its UI task.
    if((regval(32'hb000d030)&1)!=0 && regval(32'hb000d050)!=0)begin
      if(timer_remaining<=TIMER_COUNTS_PER_INSTRUCTION)begin
       timer_pending<=1;
       if((regval(32'hb000d020)&1)!=0)timer_remaining<=regval(32'hb000d050)+timer_remaining-TIMER_COUNTS_PER_INSTRUCTION;
       else begin timer_remaining<=0;csr[csr_index(32'hb000d030)]<=regval(32'hb000d030)&32'hfffffffe;end
      end else timer_remaining<=timer_remaining-TIMER_COUNTS_PER_INSTRUCTION;
    end
    if(clock_waiting)begin
     if(clock_delay>1)clock_delay<=clock_delay-1'b1;
     else begin
      clock_waiting<=0;serial_rx<=wire_byte;
      csr[csr_index(32'hb2009020)]<=regval(32'hb2009020)|1;
      if(wire_active)begin
       if(wire_pos==wire_len)wire_active<=0;
       else if(!wire_escape && (wire_raw==0 || wire_raw==8'h1b))wire_escape<=1;
       else begin wire_escape<=0;wire_pos<=wire_pos+1'b1;end
      end
      if(tx_escape)begin
       if(tx_count<16)begin tx_body[tx_count[3:0]]<=regval(32'hb2009010);tx_count<=tx_count+1'b1;end
       else model_halt<=8'he1;
       tx_escape<=0;
      end else if((regval(32'hb2009010)&255)==27)tx_escape<=1;
      else if((regval(32'hb2009010)&255)!=0)begin
       if(tx_count<16)begin tx_body[tx_count[3:0]]<=regval(32'hb2009010);tx_count<=tx_count+1'b1;end
       else model_halt<=8'he1;
      end else if(tx_count!=0)begin
       tx_count<=0;serial_frames<=serial_frames+1'b1;
       if(tx_count<3 || tx_count!={1'b0,tx_body[0]}+1)model_halt<=8'he2;
       else if(ack_pending)model_halt<=8'he3;
       else begin
        ack_pending<=1;
        if(tx_body[2]==8'h44)begin ack_body<={8'h04,tx_body[1],8'h44,8'hff,8'hff,8'd0};ack_len<=5;end
        else begin ack_body<={8'h02,tx_body[1],(tx_body[2]==8'h52 ? 8'h52 : 8'h10),24'd0};ack_len<=3;end
       end
      end
     end
    end
    if(serial0_delay!=0)begin
     serial0_delay<=serial0_delay-1'b1;
     if(serial0_delay==1)csr[csr_index(32'hb2002060)]<=regval(32'hb2002060)|2;
    end
    if(i2c_delay!=0)begin
     i2c_delay<=i2c_delay-1'b1;
     if(i2c_delay==1)begin
      csr[csr_index(32'hb2006010)]<=i2c_ack?4:0;
      csr[csr_index(32'hb2006050)]<=1;
      if(i2c_receive)begin
       i2c_receive<=0;
       if(i2c_address==8'ha1)begin
        csr[csr_index(32'hb2006040)]<={24'd0,eeprom_q};ee_pointer<=ee_pointer+1'b1;
       end else if(i2c_address==8'h19)begin
        case(lsi_group)
         0:csr[csr_index(32'hb2006040)]<={24'd0,lsi_apr[7:0]};
         1:csr[csr_index(32'hb2006040)]<={27'd0,lsi_apr[12:8]};
         2:begin csr[csr_index(32'hb2006040)]<=0;lsi_apr<=lsi_apr+1'b1;end
         3:begin
          if(lsi_apr==6 || lsi_apr>33)model_halt<=8'he4;
          // Functional replay source acquisition, not a physical RF model.
          csr[csr_index(32'hb2006040)]<=lsi_apr==11 && transport_lock?32'h3f:32'd0;lsi_apr<=lsi_apr+1'b1;
         end
         4:begin
          if(lsi_apr>127)model_halt<=8'he5;
          csr[csr_index(32'hb2006040)]<={24'd0,lsi4_q};lsi_apr<=lsi_apr+1'b1;
         end
         7:csr[csr_index(32'hb2006040)]<=0;
         default:model_halt<=8'he6;
        endcase
       end else model_halt<=8'he7;
      end
     end
    end
   end
   if(gpu_done)begin gpu_pending<=1;csr[csr_index(32'hb0009010)]<=regval(32'hb0009010)&32'hffffefff;end
   if(io_req && io_ready && io_we)begin
    if(csr_index(io_addr)!=127)csr[csr_index(io_addr)]<=io_wdata;
    if(io_addr>=32'hb4080000 && io_addr<32'hb4080008)uart[io_addr[2:0]^3'b011]<=io_wdata[7:0];
    case(io_addr)
     32'hb000d030:if(io_wdata[0] && (regval(32'hb000d030)&1)==0)timer_remaining<=regval(32'hb000d050);
     32'hb000d0e0:if(io_wdata[0])begin timer_pending<=0;timer_acks<=timer_acks+1'b1;end
     // Smartcard interface event status: write-one-to-clear. The original
     // card ISR (800F2F88) reads it, acknowledges with 0xBF and later clears
     // the handled bit (800F3558 writes 4); 800F3564 writes 0 as a no-op.
     // No card is modelled, so nothing sets these bits. Plain storage here
     // made the acknowledge read back as a new card event every 20 ms.
     32'hb000b814:csr[csr_index(32'hb000b814)]<=regval(32'hb000b814)&~io_wdata;
     32'hb0009010:if(io_wdata[12])gpu_start<=1;
     32'hb0009130:if(io_wdata[12])begin gpu_pending<=0;gpu_acks<=gpu_acks+1'b1;end
     32'hb200a000:if((regval(32'hb200a000)&1)!=0 && !io_wdata[0] && (regval(32'hb2009000)&128)!=0)begin clock_waiting<=1;clock_delay<=64;end
     32'hb2002050:serial0_delay<=64;
     32'hb2006000:begin
      if(io_wdata==32'h9a)begin i2c_start<=1;i2c_first_payload<=1;end
      if(io_wdata==32'h99)begin
       i2c_address_valid<=0;i2c_delay<=0;
       if(ee_pending_count!=0)begin ee_commit_count<=ee_pending_count;ee_commit_index<=0;ee_pending_count<=0;end
      end
      if(io_wdata==32'ha8 || io_wdata==32'hac)begin i2c_receive<=1;i2c_delay<=64;end
     end
     32'hb2006040:begin
      i2c_delay<=64;
      if(i2c_start)begin
       i2c_start<=0;i2c_address<=io_wdata[7:0];i2c_address_valid<=1;ee_address_count<=0;
      end else if(i2c_address==8'ha0)begin
       if(ee_address_count==0)begin ee_address_high<=io_wdata[7:0];ee_address_count<=1;end
       else if(ee_address_count==1)begin ee_pointer<={ee_address_high,io_wdata[7:0]};ee_address_count<=2;end
       else if(ee_pending_count<256)begin
        ee_pending_addr[ee_pending_count[7:0]]<=ee_pointer;ee_pending_data[ee_pending_count[7:0]]<=io_wdata[7:0];
        ee_pending_count<=ee_pending_count+1'b1;ee_pointer<=ee_pointer+1'b1;
       end else model_halt<=8'he8;
      end else if(i2c_address==8'h18)begin
       if(i2c_first_payload)begin
        i2c_first_payload<=0;lsi_group<=io_wdata[2:0];if(io_wdata>7)model_halt<=8'he9;
       end else case(lsi_group)
        0:lsi_apr[7:0]<=io_wdata[7:0];
        1:lsi_apr[12:8]<=io_wdata[4:0];
        4:begin
         if(lsi_apr>127)model_halt<=8'he5;
         else lsi4[lsi_apr[6:0]]<=lsi_apr==55?io_wdata[7:0]&8'hfc:io_wdata[7:0];
         lsi_apr<=lsi_apr+1'b1;
        end
        2,3,5:lsi_apr<=lsi_apr+1'b1;
        7:begin end
        default:model_halt<=8'hea;
       endcase
      end
     end
     default:begin end
    endcase
   end
  end
 end
endmodule
