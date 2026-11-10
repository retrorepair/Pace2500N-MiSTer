`timescale 1ns/1ps
module tb_pal576i;
    reg clk=0,reset=1;
    always #10 clk=~clk;
    wire ce,visible,hs,vs,field;
    wire [9:0] x,y;
    pace_pal576i DUT(.clk(clk),.reset(reset),.ce_pixel(ce),.x(x),.y(y),
        .visible(visible),.hs(hs),.vs(vs),.field(field));
    integer n,row,active=0;
    integer samples[0:575];
    initial begin
        for(row=0;row<576;row=row+1) samples[row]=0;
        repeat(5) @(negedge clk);
        reset=0;
        for(n=0;n<500000;n=n+1) begin
            do @(posedge clk); while(!ce);
            if(x!==n%800) $fatal(1,"Horizontal raster discontinuity at %d",n);
            if(field!==(n>=250000)) $fatal(1,"Field phase differs at %d",n);
            if(hs!==!((n%800>=660)&&(n%800<720))) $fatal(1,"HS differs");
            if(vs!==!(n%250000<4000)) $fatal(1,"VS differs");
            if(visible) begin
                if(x>=640 || y>=576 || y[0]!==field) $fatal(1,"Active sample out of bounds");
                samples[y]=samples[y]+1;
                active=active+1;
            end
        end
        for(row=0;row<576;row=row+1)
            if(samples[row]!=640) $fatal(1,"Row %d has %d active samples",row,samples[row]);
        if(active!=368640) $fatal(1,"Active frame sample count differs");
        $display("PASS: 625-line frame, 312.5-line fields, 640x576 active samples, 15.625 kHz nominal HS");
        $finish;
    end
    initial begin #50000000; $fatal(1,"Raster timeout"); end
endmodule
