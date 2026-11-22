`timescale 1ns/1ps
module tb_teletext_live;
    reg sysclk=0,vidclk=0;
    always #27 sysclk=~sysclk; // 50MHz:54MHz ratio
    always #25 vidclk=~vidclk;
    reg reset=1,strobe=0,packet_start=0;
    reg [7:0] data=0;
    wire space,wr;
    wire [7:0] value,q;
    wire [15:0] accepted,dropped;
    pace_teletext_pes demux(.clk(sysclk),.reset(reset),.strobe(strobe),.packet_start(packet_start),.data(data),
        .space(space),.valid(wr),.value(value),.accepted(accepted),.dropped(dropped));
    // Test-only bounded dual-clock queue. Hardware uses Quartus dcfifo with
    // four-stage pointer synchronizers; tested separately by platform primitive.
    reg [7:0] memory[0:4095];
    integer write_pos=0,read_pos=0;
    assign space=write_pos-read_pos<1800;
    assign q=memory[read_pos%4096];
    always @(posedge sysclk)if(!reset && wr)begin memory[write_pos%4096]<=value;write_pos<=write_pos+1;end
    wire pop;
    always @(posedge vidclk)if(!reset && pop)read_pos<=read_pos+1;
    integer raster=0;
    always @(posedge vidclk)raster<=raster==2159999 ? 0:raster+1;
    wire hs=raster%3456<256,vs=raster%1080000<17280;
    wire sync_n=!(hs^vs),out;
    wire [31:0] status;
    pace_teletext_test #(.LIVE(1)) tx(.clk(vidclk),.reset(reset),.allowed(1'b1),.trigger_toggle(1'b0),
        .hsync(hs),.vsync(vs),.sync_n(sync_n),.live_enable(1'b1),.stream_reset(reset),
        .packet_available(write_pos-read_pos>=45),.packet_data(q),.packet_read(pop),.hs_out(out),.debug_state(status));
    reg [7:0] input_bytes[0:32767];
    integer count=0,i,j;
    initial begin
        $readmemh("/tmp/pace-live-text-input.hex",input_bytes);
        if(!$value$plusargs("BYTES=%d",count))$fatal(1,"BYTES missing");
        repeat(10)@(negedge sysclk);reset=0;
        for(i=0;i<count;i=i+1)begin
            @(negedge sysclk);strobe=1;packet_start=i%188==0;data=input_bytes[i];
            // 64 clocks/byte is the actual6.25Mbit/s replay rate.
            @(negedge sysclk);strobe=0;repeat(62)@(negedge sysclk);
            if(i%188==187)repeat(400000)@(negedge sysclk); // bounded PC carousel rate
        end
        // Drain queued packets. No more than14lines/field accepted.
        repeat(12000000)@(negedge vidclk);
        if(write_pos!=read_pos)$fatal(1,"Incomplete FIFO drain %d %d",write_pos,read_pos);
        if(read_pos<45*30 || read_pos%45!=0)$fatal(1,"Too few/misaligned lines %d",read_pos);
        if(accepted<10 || dropped!=0)$fatal(1,"Unexpected PES stats %d %d",accepted,dropped);
        $fclose(file);
        $display("PASS live TS->PES->dual-clock queue->physical VBI: %d lines, %d PES packets",packet_count,accepted);
        $finish;
    end
    integer file,packet_count=0,age=0,bit_no=0,next_bit,ones=0,width=0,idx;
    reg old_busy=0;
    reg [359:0] bits=0;
    initial file=$fopen("/tmp/pace-live-text-output.hex","w");
    always @(negedge vidclk)begin
        if(!status[31] && out!==sync_n)$fatal(1,"Inactive CSync changed");
        if(status[31] && !sync_n && out!==0)$fatal(1,"Sync not zero");
        if(status[29] && !old_busy)begin age=0;bit_no=0;ones=0;width=0;bits=0;end
        if(status[29] || old_busy)begin
            next_bit=age*37/288;
            if(next_bit>bit_no || !status[29])begin
                if(width<7 || width>8)$fatal(1,"Bad bit width");
                bits[bit_no]=ones>=width-1;bit_no=next_bit;ones=0;width=0;
            end
            if(status[29])begin
                if(out)ones=ones+1;width=width+1;age=age+1;
            end else begin
                if(age!=2803)$fatal(1,"Truncated packet");
                for(idx=0;idx<45;idx=idx+1)$fwrite(file,"%02x",bits[idx*8+:8]);
                $fwrite(file,"\n");packet_count=packet_count+1;
            end
        end
        old_busy=status[29];
    end
    initial begin #2000000000;$fatal(1,"Timeout");end
endmodule
