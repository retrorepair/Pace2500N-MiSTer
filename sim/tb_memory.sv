`timescale 1ns/1ps
// Synthetic instructions isolate CPU DDR byte order and stalls from real boot.
module tb_memory;
    reg clk=0,reset=1;
    always #10 clk=~clk;
    wire req,we;
    wire [28:0] addr;
    wire [63:0] wdata;
    wire [7:0] be;
    wire [7:0] halt;
    reg rvalid=0;
    reg [63:0] rdata=0;
    reg [63:0] memory=0;
    reg [31:0] cycles=0;
    wire accept=req && cycles[1:0]==2;
    integer pending=0,lane,n,phase,program_length;
    reg [31:0] expected;
    pace_firmware_cpu DUT(.clk(clk),.reset(reset),.full_flash_loaded(1'b0),.mmio_policy(2'd0),
        .mem_req(req),.mem_we(we),.mem_addr(addr),.mem_wdata(wdata),.mem_be(be),
        .mem_accept(accept),.mem_rvalid(rvalid),.mem_rdata(rdata),.halt_code(halt),
        .pc(),.instruction(),.retired(),.ram_writes(),.last_ram_address(),
        .last_mmio_address(),.last_mmio_value(),.last_mmio_read(),.mmio_writes(),
        .guessed_reads(),.mips16(),.reached_mips16());
    always @(posedge clk) begin
        cycles<=cycles+1;
        rvalid<=0;
        if(pending>0) begin
            pending<=pending-1;
            if(pending==1) begin rvalid<=1; rdata<=memory; end
        end
        if(!reset && req && accept) begin
            if(addr!==29'h06000000) $fatal(1,"Incorrect DDR address %h",addr);
            if(we) begin
                for(lane=0;lane<8;lane=lane+1)
                    if(be[lane]) memory[lane*8 +:8]<=wdata[lane*8 +:8];
            end else begin
                if(pending!=0) $fatal(1,"Overlapping reads");
                pending<=3;
            end
        end
    end
    task emit(input [31:0] code);
        begin DUT.boot_memory.words[program_length]=code; program_length=program_length+1; end
    endtask
    function [31:0] op(input [5:0] opcode,input [4:0] rs,rt,input [15:0] imm);
        op={opcode,rs,rt,imm};
    endfunction
    initial begin
        // Byte, halfword, word accesses at every naturally aligned lane.
        for(phase=0;phase<3;phase=phase+1) begin
            reset=1; memory=0;
            repeat(5) @(negedge clk);
            program_length=0;
            emit(op(15,0,1,16'ha000));
            for(n=0;n<(8>>phase);n=n+1) begin
                if(phase==0) emit(op(13,0,2,16'h0080+n));
                else if(phase==1) emit(op(13,0,2,16'h8120+n));
                else begin emit(op(15,0,2,16'h89ab)); emit(op(13,2,2,16'hcdef+n)); end
                emit(op(40+phase,1,2,n<<phase)); // SB, SH, then SW uses opcode 43
                if(phase==2) DUT.boot_memory.words[program_length-1]=op(43,1,2,n<<phase);
            end
            for(n=0;n<(8>>phase);n=n+1) begin
                emit(op(phase==2?35:32+phase,1,8+n,n<<phase));
                if(phase!=2) emit(op(36+phase,1,16+n,n<<phase));
            end
            emit(32'hfc000000); // Unsupported instruction is our explicit end marker.
            reset=0;
            wait(halt!=0);
            if(halt!==8'h20) $fatal(1,"Unexpected halt %h",halt);
            for(n=0;n<(8>>phase);n=n+1) begin
                expected=(phase==0)?32'hffffff80+n:(phase==1)?32'hffff8120+n:32'h89abcdef+n;
                if(DUT.gpr[8+n]!==expected) $fatal(1,"Signed load phase=%d lane=%d",phase,n);
                if(phase!=2 && DUT.gpr[16+n]!==((phase==0)?32'h80+n:32'h8120+n))
                    $fatal(1,"Unsigned load phase=%d lane=%d",phase,n);
            end
            if(phase==0 && memory!==64'h8786858483828180) $fatal(1,"Byte stores differ %h",memory);
            if(phase==1 && memory!==64'h2381228121812081) $fatal(1,"Halfword stores differ %h",memory);
            if(phase==2 && memory!==64'hf0cdab89efcdab89) $fatal(1,"Word stores differ %h",memory);
            @(negedge clk);
        end
        $display("PASS: all byte/halfword/word DDR lanes, signed loads, request stalls and delayed reads");
        $finish;
    end
    initial begin #1000000; $fatal(1,"Memory test timeout"); end
endmodule
