`timescale 1ns/1ps
module tb_teletext_pes;
    reg clk=0;always #5 clk=~clk;
    reg reset=1,strobe=0,space=1,packet_start=0;
    reg [7:0] data=0;
    wire valid;wire [7:0] value;
    wire [15:0] accepted,dropped;
    pace_teletext_pes dut(.clk(clk),.reset(reset),.strobe(strobe),.packet_start(packet_start),.data(data),.space(space),
        .valid(valid),.value(value),.accepted(accepted),.dropped(dropped));
    reg [7:0] bytes_in[0:3759];
    integer emitted=0;
    always @(posedge clk)if(valid && !reset)begin
        if(emitted%45<2 && value!=8'h55)$fatal(1,"Run-in alignment");
        if(emitted%45==2 && value!=8'h27)$fatal(1,"Framing alignment");
        emitted<=emitted+1;
    end
    task send(input integer mode);
        integer i;reg[7:0] v;
        begin
            for(i=0;i<188;i=i+1)begin
                v=bytes_in[i];
                if(mode==1 && i==1)v=v|8'h80; // TEI
                if(mode==2 && i==53)v=0;       // bad framing
                if(mode==3 && i==2)v=v^1;     // another PID
                if(mode==4 && i==97)v=43;     // bad data-unit length
                if(mode==6 && (i==96 || i==142))v=8'hff; // legal stuffing units
                @(negedge clk);strobe=1;data=v;packet_start=i==0;
                @(negedge clk);strobe=0;
            end
            repeat(160)@(negedge clk);
        end
    endtask
    initial begin
        $readmemh("/tmp/pace-live-text-input.hex",bytes_in);
        repeat(5)@(negedge clk);reset=0;
        send(0);send(1);send(2);send(3);send(4);
        space=0;send(5);space=1;send(6);
        if(accepted!=2 || dropped!=4 || emitted!=180)$fatal(1,"Bad totals %d %d %d",accepted,dropped,emitted);
        $display("PASS atomic Teletext admission: valid/stuffing, TEI, malformed framing/length, other PID, full FIFO, packet alignment");
        $finish;
    end
endmodule
