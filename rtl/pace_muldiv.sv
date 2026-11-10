// SPDX-License-Identifier: GPL-3.0-only
// Iterative 32-bit HI/LO arithmetic: bounded hardware, 32 calculation clocks.
// operation: 0 MULT, 1 MULTU, 2 DIV, 3 DIVU. Divide by zero reports error.
module pace_muldiv (
    input wire clk, reset, start,
    input wire [1:0] operation,
    input wire [31:0] a,b,
    output reg busy=0,done=0,error=0,
    output reg [31:0] hi=0,lo=0
);
    reg divide=0,negative_product=0,negative_quotient=0,negative_remainder=0;
    reg [5:0] count=0;
    reg [63:0] multiplicand=0,product=0;
    reg [31:0] multiplier=0,quotient=0,divisor=0;
    reg [32:0] remainder=0;
    wire signed_operation=!operation[0];
    wire [31:0] magnitude_a=(signed_operation && a[31]) ? (~a+32'd1) : a;
    wire [31:0] magnitude_b=(signed_operation && b[31]) ? (~b+32'd1) : b;
    wire [63:0] product_next=product+(multiplier[0]?multiplicand:64'd0);
    wire [63:0] product_result=negative_product ? (~product_next+64'd1) : product_next;
    wire [32:0] remainder_shift={remainder[31:0],quotient[31]};
    wire subtract=remainder_shift>={1'b0,divisor};
    wire [32:0] remainder_next=subtract ? remainder_shift-{1'b0,divisor} : remainder_shift;
    wire [31:0] quotient_next={quotient[30:0],subtract};
    always @(posedge clk) begin
        done<=0;
        if(reset) begin
            busy<=0;done<=0;error<=0;hi<=0;lo<=0;count<=0;
        end else if(start && !busy) begin
            error<=0;count<=0;divide<=operation[1];
            negative_product<=signed_operation && (a[31]^b[31]);
            negative_quotient<=signed_operation && (a[31]^b[31]);
            negative_remainder<=signed_operation && a[31];
            if(operation[1] && b==0) begin
                busy<=0;done<=1;error<=1;
            end else begin
                busy<=1;
                multiplicand<={32'd0,magnitude_a};multiplier<=magnitude_b;product<=0;
                quotient<=magnitude_a;divisor<=magnitude_b;remainder<=0;
            end
        end else if(busy) begin
            count<=count+1'd1;
            if(divide) begin
                quotient<=quotient_next;remainder<=remainder_next;
                if(count==31) begin
                    lo<=negative_quotient ? (~quotient_next+32'd1) : quotient_next;
                    hi<=negative_remainder ? (~remainder_next[31:0]+32'd1) : remainder_next[31:0];
                    busy<=0;done<=1;
                end
            end else begin
                product<=product_next;multiplicand<=multiplicand<<1;multiplier<=multiplier>>1;
                if(count==31) begin hi<=product_result[63:32];lo<=product_result[31:0];busy<=0;done<=1;end
            end
        end
    end
endmodule
