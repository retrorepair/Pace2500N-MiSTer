// Testbench for rtl/pace_eeprom_save.sv: an EEPROM with the peripherals' port-B timing and an
// SD image slot answering like hps_io (WIDE=1, one 512-byte block per request).
`timescale 1ns/1ps
module tb;
 reg clk=0;always #5 clk=~clk;
 reg reset=1;
 reg img_mounted=0;reg [63:0] img_size=0;
 wire [31:0] sd_lba;wire [5:0] sd_blk_cnt;wire sd_rd,sd_wr;
 reg sd_ack=0;reg [12:0] sd_buff_addr=0;reg [15:0] sd_buff_dout=0;reg sd_buff_wr=0;
 wire [15:0] sd_buff_din;
 wire [15:0] ee_addr;wire ee_we;wire [7:0] ee_wdata;reg [7:0] ee_q=0;
 reg ee_commit_we=0;reg [15:0] ee_commit_addr=0;
 wire loading,mounted;wire [15:0] saved;
 pace_eeprom_save #(.QUIET(24'd200)) dut(.clk(clk),.reset(reset),.img_mounted(img_mounted),.img_size(img_size),
  .sd_lba(sd_lba),.sd_blk_cnt(sd_blk_cnt),.sd_rd(sd_rd),.sd_wr(sd_wr),.sd_ack(sd_ack),.sd_buff_addr(sd_buff_addr),
  .sd_buff_dout(sd_buff_dout),.sd_buff_wr(sd_buff_wr),.sd_buff_din(sd_buff_din),
  .ee_addr(ee_addr),.ee_we(ee_we),.ee_wdata(ee_wdata),.ee_q(ee_q),.ee_commit_we(ee_commit_we),.ee_commit_addr(ee_commit_addr),
  .loading(loading),.mounted(mounted),.saved_blocks(saved));
 reg [7:0] eeprom[0:65535];reg [7:0] file[0:65535];
 always @(posedge clk)begin           // port B: registered read, write
  if(ee_we)eeprom[ee_addr]<=ee_wdata;
  ee_q<=eeprom[ee_addr];
 end
 integer k,w,errors=0;reg writing=0;reg [31:0] lba=0;
 // the SD slot
 always begin
  @(posedge clk);
  if(sd_rd||sd_wr)begin
   writing=sd_wr;lba=sd_lba;
   repeat(7)@(posedge clk);
   sd_ack<=1;sd_buff_addr<=0;
   @(posedge clk);
   for(w=0;w<256;w=w+1)begin
    if(sd_rd)begin end
    sd_buff_addr<=w;
    if(!writing)begin   // read: file -> core
     sd_buff_dout<={file[lba*512+w*2+1],file[lba*512+w*2]};
     @(posedge clk);sd_buff_wr<=1;@(posedge clk);sd_buff_wr<=0;repeat(3)@(posedge clk);
    end else begin        // write: core -> file
     repeat(5)@(posedge clk);
     {file[lba*512+w*2+1],file[lba*512+w*2]}=sd_buff_din;
    end
   end
   @(posedge clk);sd_ack<=0;
   repeat(3)@(posedge clk);
  end
 end
 task mount;begin
  @(posedge clk);img_size<=65536;img_mounted<=1;@(posedge clk);img_mounted<=0;
  @(posedge clk);while(loading)@(posedge clk);
 end endtask
 task settle;begin
  // wait until nothing is marked and the engine is idle
  repeat(400)@(posedge clk);
  while(dut.dirty!=0 || dut.state!=0)@(posedge clk);
  repeat(20)@(posedge clk);
 end endtask
 task compare(input [255:0] what);begin
  for(k=0;k<65536;k=k+1)if(file[k]!==eeprom[k])begin
   if(errors<5)$display("MISMATCH %0s at %h: file %h eeprom %h",what,k,file[k],eeprom[k]);errors=errors+1;end
 end endtask
 initial begin
  for(k=0;k<65536;k=k+1)begin eeprom[k]=(k*7+k/256)&255;file[k]=8'hff;end
  repeat(5)@(posedge clk);reset<=0;
  // 1: a blank file is filled from the EEPROM
  mount;settle;compare("blank fill");
  $display("blank fill: %0d blocks saved",saved);
  // 2: a written file is loaded into the EEPROM on mount
  for(k=0;k<65536;k=k+1)file[k]=(k*13+5)&255;
  for(k=0;k<65536;k=k+1)eeprom[k]=8'h00;
  mount;compare("load");
  if(dut.dirty!=0)begin $display("FAIL: blocks marked after a load");errors=errors+1;end
  // 3: committed writes reach the file (two blocks, including one during a save)
  for(k=0;k<40;k=k+1)begin
   @(posedge clk);ee_commit_we<=1;ee_commit_addr<=16'h3f00+k*3;eeprom[16'h3f00+k*3]=8'h5a+k;
   @(posedge clk);ee_commit_we<=0;
  end
  settle;compare("save");
  $display("after writes: %0d blocks saved",saved);
  if(errors==0)$display("PASS");else $display("FAIL: %0d mismatches",errors);
  $finish;
 end
 initial begin #400000000;$display("TIMEOUT");$finish;end
endmodule
