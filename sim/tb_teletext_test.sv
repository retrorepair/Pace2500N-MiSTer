`timescale 1ns/1ps
module tb_teletext_test;
    reg clk=0;
    always #1 clk=~clk;
    reg reset=1,allowed=1,trigger=0;
    integer raster=0;
    reg bad_rate=0,missing_hs=0;
    wire hs=!missing_hs && (raster% (bad_rate ? 3400:3456))<256;
    // 625 half-lines/field, including the half-line interlace displacement.
    wire vs=(raster%1080000)<17280;
    wire sync_n=!(hs^vs);
    wire out;
    wire [31:0] state;
    pace_teletext_test #(.TEST_CYCLES(60000000)) dut(
        .clk(clk),.reset(reset),.allowed(allowed),.trigger_toggle(trigger),
        .hsync(hs),.vsync(vs),.sync_n(sync_n),.hs_out(out),.debug_state(state));
    always @(posedge clk)raster<=raster==2159999 ? 0:raster+1;
    integer cycles=0,packet_count=0,packet_age=0,bit_no=0,next_bit,ones=0,width=0;
    integer file,idx;
    reg previous_busy=0;
    reg capture=0;
    reg [359:0] bits=0;
    // Decode the PHYSICAL one-bit output, integrating each 7/8-clock bit.
    // Neither ROM contents nor the serializer shift register is inspected.
    always @(negedge clk)begin
        cycles=cycles+1;
        if(!state[31] && out!==sync_n)$fatal(1,"Inactive output changed CSync");
        if(state[31] && !sync_n && out!==0)$fatal(1,"Sync pulse not at zero");
        if(state[29] && !previous_busy)begin
            packet_age=0;bit_no=0;ones=0;width=0;bits=0;
            if(dut.line_cycle!=555)$fatal(1,"Wrong packet start %d",dut.line_cycle);
        end
        if(state[29] || previous_busy)begin
            next_bit=(packet_age*37)/288;
            if(next_bit>bit_no || !state[29])begin
                if(width<7 || width>8)$fatal(1,"Wrong bit width %d",width);
                bits[bit_no]=(ones>=width-1);
                bit_no=next_bit;ones=0;width=0;
            end
            if(state[29])begin
                if(out)ones=ones+1;
                width=width+1;
                packet_age=packet_age+1;
            end else begin
                if(packet_age!=2803)$fatal(1,"Packet length %d",packet_age);
                if(capture)begin
                    for(idx=0;idx<45;idx=idx+1)$fwrite(file,"%02x",bits[idx*8+:8]);
                    $fwrite(file,"\n");packet_count=packet_count+1;
                end
            end
        end
        previous_busy=state[29];
    end
    task press;
        begin @(negedge clk);trigger=~trigger;repeat(6)@(negedge clk);end
    endtask
    integer high_count;
    initial begin
        file=$fopen("/tmp/pace-ttx-packets.hex","w");
        repeat(10)@(negedge clk);reset=0;
        repeat(15000)@(negedge clk);
        if(!state[30])$fatal(1,"PAL line lock missing");
        press();if(!state[31])$fatal(1,"Trigger did not start");
        // Pedestal density exact over an integer number of accumulator cycles.
        wait(!hs && dut.field_line>20);@(negedge clk);
        high_count=0;
        repeat(1270)begin @(negedge clk);if(out)high_count=high_count+1;end
        if(high_count!=500)$fatal(1,"Black density %d",high_count);
        press();if(state[31])$fatal(1,"Trigger did not cancel");
        press();allowed=0;repeat(8)@(negedge clk);
        if(state[31] || state[28])$fatal(1,"Disallowed mode did not stop");
        allowed=1;press();bad_rate=1;
        repeat(10000)@(negedge clk);
        if(state[31] || state[30])$fatal(1,"Bad line frequency accepted");
        bad_rate=0;press(); // cancel previous window
        repeat(15000)@(negedge clk);
        press();missing_hs=1;repeat(7000)@(negedge clk);
        if(state[31] || state[30])$fatal(1,"Missing HS accepted");
        missing_hs=0;press();repeat(15000)@(negedge clk);
        // Full page carousel, automatic window expiry, both interlaced fields.
        capture=1;press();repeat(60000010)@(negedge clk);
        if(state[31] || state[28])$fatal(1,"Automatic timeout failed");
        if(packet_count<50)$fatal(1,"Not enough page packets %d",packet_count);
        $fclose(file);
        $display("PASS TTX: %d physical-output packets, PDM density, both fields, cancel, timeout, rate/missing-HS guards, inactive CSync",packet_count);
        $finish;
    end
endmodule
