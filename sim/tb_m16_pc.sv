`timescale 1ns/1ps
// MD00076 table 3-14: current PC, JR origin, and two-halfword JAL origin.
module tb_m16_pc;
    reg clk=0,reset=1;
    always #10 clk=~clk;
    wire [7:0] halt;
    wire req;
    integer phase,n;
    pace_firmware_cpu DUT(.clk(clk),.reset(reset),.full_flash_loaded(1'b0),.mmio_policy(2'd0),
        .mem_req(req),.mem_we(),.mem_addr(),.mem_wdata(),.mem_be(),
        .mem_accept(1'b0),.mem_rvalid(1'b0),.mem_rdata(64'd0),.halt_code(halt),
        .pc(),.instruction(),.retired(),.ram_writes(),.last_ram_address(),
        .last_mmio_address(),.last_mmio_value(),.last_mmio_read(),.mmio_writes(),
        .guessed_reads(),.mips16(),.reached_mips16());
    task half(input integer address,input [15:0] code);
        if(address%4==0) DUT.boot_memory.words[address/4][31:16]=code;
        else DUT.boot_memory.words[address/4][15:0]=code;
    endtask
    initial begin
        for(phase=0;phase<5;phase=phase+1) begin
            reset=1;
            repeat(5) @(negedge clk);
            DUT.boot_memory.words[0]=32'h77f00040; // MIPS32 JALX BFC00100
            DUT.boot_memory.words[1]=0;
            DUT.boot_memory.words[2]=32'hfc000000; // MIPS32 end marker
            for(n=64;n<128;n=n+1) DUT.boot_memory.words[n]=32'hf800f800;
            DUT.boot_memory.words[80]=32'h11223344;
            DUT.boot_memory.words[81]=32'hdeadbeef;
            case(phase)
                0: begin
                    half('h100,16'h0a01); // ADDIU v0,pc,4
                    half('h102,16'hb310); // LW v1,0x40(pc)
                    half('h104,16'he820); half('h106,16'h4800); // JR ra; NOP
                end
                1,2: begin
                    half('h100,16'h6c00); half('h102,16'he820); // LI a0,0; JR ra
                    half('h104,phase==1?16'h0a01:16'hb310);
                end
                3: begin
                    half('h100,16'h1a1f); half('h102,16'h0060); // JAL BFC00180
                    half('h104,16'h0a01);
                end
                4: begin
                    half('h100,16'h6c00);
                    half('h102,16'h1a1f); half('h104,16'h0060);
                    half('h106,16'h0a01);
                end
            endcase
            reset=0;
            wait(halt!=0);
            if(req) $fatal(1,"Unexpected DDR request");
            if(halt!==((phase<3)?8'h20:8'h30)) $fatal(1,"Unexpected halt phase=%d code=%h",phase,halt);
            if(phase!=2 && DUT.gpr[2]!==32'hbfc00104) $fatal(1,"ADDIUPC base differs phase=%d value=%h",phase,DUT.gpr[2]);
            if((phase==0 || phase==2) && DUT.gpr[3]!==32'h11223344) $fatal(1,"LWPC base differs phase=%d",phase);
            @(negedge clk);
        end
        $display("PASS: MIPS16 PC-relative bases, normal and JR/JAL delay slots, both JAL halfword alignments");
        $finish;
    end
    initial begin #1000000; $fatal(1,"MIPS16 PC test timeout"); end
endmodule
