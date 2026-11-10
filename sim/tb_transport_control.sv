`timescale 1ns/1ps
module tb_transport_control;
 reg clk=0,reset=1;always #5 clk=~clk;
 reg download=0,wr=0;reg[26:0] address=0;wire loaded;wire[23:0] length;
 pace_ts_load_tracker tracker(.clk(clk),.reset(reset),.download(download),.wr(wr),.address(address),.loaded(loaded),.length(length));
 reg hold=0,cpu_req=0,device_ready=0;reg[31:0] device_data=0;
 wire cpu_ready,device_req;wire[31:0] cpu_data;
 pace_mmio_response bus(.clk(clk),.reset(reset),.hold(hold),.cpu_req(cpu_req),
  .cpu_ready(cpu_ready),.cpu_data(cpu_data),.device_req(device_req),.device_ready(device_ready),.device_data(device_data));
 integer accepted=0;
 always @(posedge clk)if(!reset && device_req && device_ready)accepted<=accepted+1;
 task transfer(input integer bytes,input integer bad_word,input integer expect_loaded);
 integer i;
 begin
  @(negedge clk);download=1;wr=0;
  @(negedge clk);
  for(i=0;i<bytes/2;i=i+1)begin wr=1;address=i*2+(i==bad_word?2:0);@(negedge clk);end
  wr=0;download=0;repeat(2)@(negedge clk);
  if(loaded!=expect_loaded || length!=(expect_loaded?bytes:0))$fatal(1,"load %d badword %d => %d length %d",bytes,bad_word,loaded,length);
 end endtask
 initial begin
  repeat(4)@(negedge clk);reset=0;
  transfer(188,-1,1);transfer(0,-1,0);transfer(186,-1,0);transfer(376,-1,1);
  transfer(188,12,0);transfer(1048476,-1,1);transfer(1048664,-1,0);
  // Slow device: no CPU response until actual acceptance.
  cpu_req=1;device_ready=0;device_data=32'h12345678;
  repeat(5)begin @(negedge clk);if(cpu_ready)$fatal(1,"early response");end
  device_ready=1;@(negedge clk);
  if(!cpu_ready || cpu_data!=32'h12345678 || accepted!=1)$fatal(1,"missing registered response");
  // Download hold can begin after a side effect. Preserve the response and
  // suppress a duplicate transaction when the CPU resumes.
  hold=1;device_data=32'hdeadbeef;
  repeat(8)begin @(negedge clk);if(device_req || cpu_ready)$fatal(1,"bus active during hold");end
  hold=0;#1;if(!cpu_ready || cpu_data!=32'h12345678)$fatal(1,"lost held response");
  @(negedge clk);cpu_req=0;
  if(accepted!=1 || cpu_ready)$fatal(1,"replayed side effect");
  $display("PASS transport control: valid/empty/misaligned/gapped/max/oversize files; MMIO stalls, held response, exactly one side effect");$finish;
 end
 initial begin #20000000;$fatal(1,"timeout");end
endmodule
