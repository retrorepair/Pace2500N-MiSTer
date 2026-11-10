// SPDX-License-Identifier: GPL-3.0-only
// One outstanding peripheral transaction, registered CPU response. A response
// survives download hold so an already accepted side effect is never replayed.
module pace_mmio_response(
 input wire clk,reset,hold,cpu_req,
 output wire cpu_ready,output reg [31:0] cpu_data=0,
 output wire device_req,input wire device_ready,input wire [31:0] device_data
);
 reg response=0;
 assign device_req=cpu_req && !response && !hold;
 assign cpu_ready=response && !hold;
 always @(posedge clk)begin
  if(reset)begin response<=0;cpu_data<=0;end
  else if(!hold)begin
   if(response)response<=0;
   else if(cpu_req && device_ready)begin cpu_data<=device_data;response<=1;end
  end
 end
endmodule
