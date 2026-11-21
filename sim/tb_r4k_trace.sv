`timescale 1ns/1ps
module tb_r4k_trace;
reg clk_sys=0,clk1x=0,clk2x=0;
always #10 clk_sys=~clk_sys;
always #14 clk1x=~clk1x;
always #7 clk2x=~clk2x;
reg reset=1,trace_reset=1,trigger=0;
wire frozen;
pace_r4k #(.TRACE_PC(32'h8003a928),.TRACE_STACKFAULT(1)) dut(
 .clk_sys(clk_sys),.clk1x(clk1x),.clk2x(clk2x),.reset_sys(reset),.trace_reset(trace_reset),
 .hold_sys(1'b1),.ckpt_loaded(1'b0),.state_wr(1'b0),.state_index(7'd0),.state_data(32'd0),
 .io_irq(1'b0),.ddr_accept(1'b0),.ddr_rvalid(1'b0),.ddr_rdata(64'd0),
 .io_rdata(32'd0),.io_ready(1'b0),.trace_next(1'b0),.trace_trigger(trigger),.trace_frozen(frozen));
initial begin
 force dut.wb_valid=1'b0;
 force dut.wb_pc=32'h800d35e8;
 #200; trace_reset=0; reset=0;
 #200; force dut.wb_valid=1'b1;
 #100; force dut.wb_pc=32'h8003a929;
 #100; force dut.wb_valid=1'b0;
 if(!frozen) $fatal(1,"Reboot routine did not freeze the instruction trace");
 reset=1;
 #200;
 if(!frozen) $fatal(1,"Board warm reset discarded the instruction trace");
 trace_reset=1;
 #200;
 if(frozen) $fatal(1,"Full core reset failed to clear the instruction trace");
 trace_reset=0;
 force dut.wb_valid=1'b1;
 force dut.wb_pc=32'hbfc0ee4c;
 force dut.wb_rd=6'h3d;
 force dut.wb_data=32'h802aacd0;
 #200;
 if(frozen) $fatal(1,"Valid loader stack triggered the error trace");
 force dut.wb_data=32'hffffff68;
 #200;
 if(!frozen) $fatal(1,"Invalid loader stack did not freeze the trace");
 trace_reset=1;
 force dut.wb_valid=0;
 #200;
 trace_reset=0; trigger=1;
 #200;
 if(!frozen) $fatal(1,"External error did not freeze the trace");
 $display("PASS: reboot trigger freezes the trace, warm reset preserves it, full reset clears it");
 $finish;
end
endmodule
