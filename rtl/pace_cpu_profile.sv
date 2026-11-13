// SPDX-License-Identifier: GPL-3.0-only
// Diagnostic cycle profiler for pace_firmware_cpu: free-running counters of
// where the core clock goes, sampled by pace_debug_uart (PROF line, once per
// second; the HPS takes differences). Read-only: observes the CPU's state.
//  0 all cycles while running      8 MMIO (device registers)
//  1 FETCH + BOUNDARY              9 boot block M10K (fetch/load)
//  2 I-cache lookup/check         10 multiply/divide
//  3 EXEC                         11 MIPS16 JAL/EXTEND second half
//  4 fetch from DDR (miss/uncached)  12 RAM loads (count)
//  5 RAM load DDR wait            13 flash loads (count)
//  6 flash load DDR wait          14 stores (count)
//  7 store DDR wait               15 instruction fetches from DDR (count)
module pace_cpu_profile(
    input wire clk, reset, hold,
    input wire [4:0] state,
    input wire [1:0] bus_kind,
    input wire bus_rom,
    output wire [511:0] counters
);
    // pace_firmware_cpu state and bus-kind encodings.
    localparam [4:0] S_FETCH=0, S_ROMFETCH=1, S_EXEC=2, S_ROMLOAD=3, S_BUSREQ=4, S_BUSWAIT=5,
                     S_BUSCOMPLETE=6, S_HALT=7, S_M16_JUMP=8, S_ROMREAD=9, S_M16_EXTEND=10,
                     S_MULDIV=11, S_MMIO=12, S_BOUNDARY=13, S_ILOOKUP=14, S_ICHECK=15, S_DECODE=16;
    localparam [1:0] K_FETCH=0, K_LOAD=1, K_STORE=2, K_HALF=3;
    reg [31:0] c[0:15];
    reg [4:0] last_state=S_FETCH;
    integer i;
    initial for(i=0;i<16;i=i+1)c[i]=0;
    wire bus=state==S_BUSREQ || state==S_BUSWAIT || state==S_BUSCOMPLETE;
    wire fetchkind=bus_kind==K_FETCH || bus_kind==K_HALF;
    wire entering=state==S_BUSREQ && last_state!=S_BUSREQ;
    always @(posedge clk) begin
        last_state<=state;
        if(reset) begin
            for(i=0;i<16;i=i+1)c[i]<=0;
        end else if(!hold && state!=S_HALT) begin
            c[0]<=c[0]+1;
            if(state==S_FETCH || state==S_BOUNDARY)c[1]<=c[1]+1;
            if(state==S_ILOOKUP || state==S_ICHECK)c[2]<=c[2]+1;
            if(state==S_EXEC || state==S_DECODE)c[3]<=c[3]+1;
            if(bus && fetchkind)c[4]<=c[4]+1;
            if(bus && bus_kind==K_LOAD && !bus_rom)c[5]<=c[5]+1;
            if(bus && bus_kind==K_LOAD && bus_rom)c[6]<=c[6]+1;
            if(bus && bus_kind==K_STORE)c[7]<=c[7]+1;
            if(state==S_MMIO)c[8]<=c[8]+1;
            if(state==S_ROMREAD || state==S_ROMFETCH || state==S_ROMLOAD)c[9]<=c[9]+1;
            if(state==S_MULDIV)c[10]<=c[10]+1;
            if(state==S_M16_JUMP || state==S_M16_EXTEND)c[11]<=c[11]+1;
            if(entering && bus_kind==K_LOAD && !bus_rom)c[12]<=c[12]+1;
            if(entering && bus_kind==K_LOAD && bus_rom)c[13]<=c[13]+1;
            if(entering && bus_kind==K_STORE)c[14]<=c[14]+1;
            if(entering && fetchkind)c[15]<=c[15]+1;
        end
    end
    genvar g;
    generate for(g=0;g<16;g=g+1) begin : pack
        assign counters[g*32 +: 32]=c[g];
    end endgenerate
endmodule
