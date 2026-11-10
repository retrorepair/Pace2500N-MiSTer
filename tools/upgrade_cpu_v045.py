"""One-shot reproducible edit from the preserved v044 CPU checkpoint."""
from pathlib import Path
p=Path('rtl/pace_firmware_cpu.sv')
s=p.read_text()
assert 'S_M16_EXTEND' not in s
s=s.replace('S_ROMREAD=9;', 'S_ROMREAD=9, S_M16_EXTEND=10, S_MULDIV=11;')
s=s.replace('K_FETCH=0, K_LOAD=1, K_STORE=2;', 'K_FETCH=0, K_LOAD=1, K_STORE=2, K_HALF=3;')
s=s.replace('reg [15:0] jump_first=0;', '''reg [15:0] jump_first=0, extend_prefix=0, extend_suffix=0;
    reg m16_extended=0, second_from_bus=0;
    reg [3:0] second_next_state=0;
    reg [31:0] second_word=0;
    wire [31:0] second_data=second_from_bus ? second_word : rom_q;
    wire [15:0] second_half=pc[1] ? second_data[31:16] : second_data[15:0];
    reg mul_start=0;
    reg [1:0] mul_operation=0;
    reg [31:0] mul_a=0,mul_b=0;
    wire mul_busy,mul_done,mul_error;
    wire [31:0] mul_hi,mul_lo;
    pace_muldiv arithmetic(.clk(clk),.reset(reset),.start(mul_start),
      .operation(mul_operation),.a(mul_a),.b(mul_b),.busy(mul_busy),
      .done(mul_done),.error(mul_error),.hi(mul_hi),.lo(mul_lo));''')
s=s.replace('assign mem_be = ((load_size==2)', "assign mem_be = bus_kind!=K_STORE ? 8'hff : ((load_size==2)")
s=s.replace('retired <= retired+1\'d1;', "m16_extended <= 0;\n            retired <= retired+1'd1;")
at='    // Prepare a read or write of actual guest memory.'
s=s.replace(at,'''    task automatic request_second(input [3:0] resume_state);
        reg [31:0] address;
        begin
            address=pc+32'd2;
            second_next_state<=resume_state;
            if((((address&32'hffe00000)==32'hbfc00000) ||
                ((address&32'hffe00000)==32'h9fc00000)) &&
                (address&32'h001fffff)<32'h20000) begin
                second_from_bus<=0;
                request_rom(address[16:2],resume_state);
            end else if(((((address&32'hffe00000)==32'hbfc00000) ||
                          ((address&32'hffe00000)==32'h9fc00000)) && full_flash_loaded) ||
                        (address&32'hff000000)==32'h80000000 ||
                        (address&32'hff000000)==32'ha0000000) begin
                second_from_bus<=1;bus_virtual<={address[31:2],2'b00};
                bus_kind<=K_HALF;state<=S_BUSREQ;
            end else halt(8'h34);
        end
    endtask
    task automatic start_arithmetic(input [1:0] operation,
                                   input [31:0] lhs,rhs);
        begin
            mul_operation<=operation;mul_a<=lhs;mul_b<=rhs;
            mul_start<=1;state<=S_MULDIV;
        end
    endtask
'''+at)
s=s.replace("pc+(mips16?32'd2:32'd4)", 'mips16?seq16:seq32')
s=s.replace('wire [15:0] m16 = pc[1] ? ir[15:0] : ir[31:16];', 'wire [15:0] m16 = m16_extended ? extend_suffix : (pc[1] ? ir[15:0] : ir[31:16]);')
s=s.replace("wire [31:0] seq16=pc+32'd2;", "wire [31:0] seq16=pc+(m16_extended?32'd4:32'd2);")
s=s.replace('    integer j;', '''    wire [15:0] ext_imm={extend_prefix[4:0],extend_prefix[10:5],m16[4:0]};
    wire [31:0] ext_signed=sext16(ext_imm);
    wire [31:0] m16_simm=m16_extended ? ext_signed : imm8se;
    wire [31:0] m16_uimm=m16_extended ? {16'd0,ext_imm} : {24'd0,m16[7:0]};
    wire [31:0] sp_offset=m16_extended ? ext_signed : ({24'd0,m16[7:0]}<<2);
    wire [31:0] off_byte=m16_extended ? ext_signed : {27'd0,m16[4:0]};
    wire [31:0] off_half=m16_extended ? ext_signed : ({27'd0,m16[4:0]}<<1);
    wire [31:0] off_word=m16_extended ? ext_signed : ({27'd0,m16[4:0]}<<2);
    wire [4:0] shift_amount=m16_extended ? extend_prefix[10:6] : (rz==0?5'd8:{2'd0,rz});
    wire [14:0] rr_imm={extend_prefix[3:0],extend_prefix[10:4],m16[3:0]};
    wire [31:0] rr_signed=m16_extended ? {{17{rr_imm[14]}},rr_imm} : {{28{m16[3]}},m16[3:0]};
    wire [4:0] full_dest={m16[4:3],ry};
    wire [31:0] jr16_target=m16[5] ? gpr[31] : rxv;
    integer j;''')
s=s.replace('hi<=0;lo<=0;', 'hi<=0;lo<=0;m16_extended<=0;mul_start<=0;second_from_bus<=0;')
s=s.replace('            gpr[0]<=0;', '            gpr[0]<=0;mul_start<=0;')
s=s.replace('end else if(pc_is_rom && full_flash_loaded) begin', '''end else if((pc_is_rom && full_flash_loaded) ||
                                (pc&32'hff000000)==32'h80000000 ||
                                (pc&32'hff000000)==32'ha0000000) begin''')
s=s.replace('                          32,33:begin', '                          24,25,26,27:start_arithmetic(fn[1:0],a,b);\n                          32,33:begin')
s=s.replace('if(rt==0 || rt==1 || rt==16 || rt==17) begin', 'if(rt==0 || rt==1 || rt==2 || rt==3 || rt==16 || rt==17 || rt==18 || rt==19) begin')
s=s.replace('if(rt==16 || rt==17)gpr[31]<=pc+8;', 'if(rt[4])gpr[31]<=pc+8;\n                              if(rt[1] && !(rt[0]?($signed(a)>=0):($signed(a)<0)))retire(seq32+4,0,0,0);\n                              else')
s=s.replace('16:begin // MFC0/MTC0; RFE/ERET not yet modelled', '16:begin // MFC0/MTC0 and architectural ERET state')
s=s.replace('else halt(8\'h12);', '''else if(ir==32'h42000018)begin
                              pc<=(cp0[12][2] ? cp0[30] : cp0[14])&32'hfffffffe;
                              mips16<=cp0[12][2] ? cp0[30][0] : cp0[14][0];
                              if(cp0[12][2])cp0[12][2]<=0;else cp0[12][1]<=0;
                              branch_pending<=0;retired<=retired+1'd1;state<=S_FETCH;
                          end else halt(8'h12);''')
start=s.index('                        0:begin // addiusp')
end=s.index('                        default:halt(8\'h30);',start)
s=s[:start]+'''                        0:begin gpr[rxg]<=gpr[29]+sp_offset;retire(seq16,0,0,1);end
                        1:begin
                          gpr[rxg]<=m16_extended ? (pc&32'hfffffffc)+ext_signed :
                                                   (m16_base_pc&32'hfffffffc)+sp_offset;
                          retire(seq16,0,0,1);
                        end
                        2:retire(seq16+((m16_extended ? ext_signed : {{21{m16[10]}},m16[10:0]})<<1),0,0,1);
                        3:begin
                          if(m16_extended || branch_pending)halt(8'h34);
                          else begin jump_first<=m16;request_second(S_M16_JUMP);end
                        end
                        4:retire(rxv==0 ? seq16+(m16_simm<<1):seq16,0,0,1);
                        5:retire(rxv!=0 ? seq16+(m16_simm<<1):seq16,0,0,1);
                        6:begin
                          if(m16[1:0]==1 || (m16_extended && (extend_prefix[5:0]!=0 || m16[4:2]!=0)))halt(8'h33);
                          else begin
                            case(m16[1:0])
                              0:gpr[rxg]<=ryv<<shift_amount;
                              2:gpr[rxg]<=ryv>>shift_amount;
                              3:gpr[rxg]<=$signed(ryv)>>>shift_amount;
                            endcase
                            retire(seq16,0,0,1);
                          end
                        end
                        8:begin
                          if(m16[4])halt(8'h30);
                          else begin gpr[ryg]<=rxv+rr_signed;retire(seq16,0,0,1);end
                        end
                        9:begin gpr[rxg]<=rxv+m16_simm;retire(seq16,0,0,1);end
                        10:begin gpr[24]<=($signed(rxv)<$signed(m16_uimm));retire(seq16,0,0,1);end
                        11:begin gpr[24]<=(rxv<m16_uimm);retire(seq16,0,0,1);end
                        12:begin
                          case(rx)
                            0:retire(gpr[24]==0 ? seq16+(m16_simm<<1):seq16,0,0,1);
                            1:retire(gpr[24]!=0 ? seq16+(m16_simm<<1):seq16,0,0,1);
                            2:access(gpr[29]+sp_offset,2,0,0,1,gpr[31]);
                            3:begin gpr[29]<=gpr[29]+(m16_extended?ext_signed:(imm8se<<3));retire(seq16,0,0,1);end
                            5:begin
                              if(m16_extended)halt(8'h31);
                              else begin if(full_dest!=0)gpr[full_dest]<=gpr[reg16(m16[2:0])];retire(seq16,0,0,1);end
                            end
                            7:begin
                              if(m16_extended)halt(8'h31);
                              else begin gpr[ryg]<=gpr[m16[4:0]];retire(seq16,0,0,1);end
                            end
                            default:halt(8'h31);
                          endcase
                        end
                        13:begin gpr[rxg]<=m16_uimm;retire(seq16,0,0,1);end
                        14:begin gpr[24]<=rxv^m16_uimm;retire(seq16,0,0,1);end
                        16:access(rxv+off_byte,0,1,ryg,0,0);
                        17:access(rxv+off_half,1,1,ryg,0,0);
                        18:access(gpr[29]+sp_offset,2,0,rxg,0,0);
                        19:access(rxv+off_word,2,0,ryg,0,0);
                        20:access(rxv+off_byte,0,0,ryg,0,0);
                        21:access(rxv+off_half,1,0,ryg,0,0);
                        22:access(m16_extended ? ((pc+ext_signed)&32'hfffffffc) :
                                   ((m16_base_pc+sp_offset)&32'hfffffffc),2,0,rxg,0,0);
                        24:access(rxv+off_byte,0,0,0,1,ryv);
                        25:access(rxv+off_half,1,0,0,1,ryv);
                        26:access(gpr[29]+sp_offset,2,0,0,1,rxv);
                        27:access(rxv+off_word,2,0,0,1,ryv);
                        28:begin
                          if(m16_extended || (m16[1:0]!=1 && m16[1:0]!=3))halt(8'h32);
                          else begin gpr[rzg]<=m16[1] ? rxv-ryv : rxv+ryv;retire(seq16,0,0,1);end
                        end
                        29:begin
                          if(m16_extended)halt(8'h32);
                          else case(m16[4:0])
                            0:begin
                              if(m16[6])gpr[31]<=(pc+(m16[7]?32'd2:32'd4))|32'd1;
                              if(m16[7])begin
                                pc<=jr16_target&32'hfffffffe;mips16<=jr16_target[0];
                                retired<=retired+1'd1;state<=S_FETCH;
                              end else retire(seq16,1,jr16_target&32'hfffffffe,jr16_target[0]);
                            end
                            2:begin gpr[24]<=($signed(rxv)<$signed(ryv));retire(seq16,0,0,1);end
                            3:begin gpr[24]<=(rxv<ryv);retire(seq16,0,0,1);end
                            4:begin gpr[ryg]<=ryv<<rxv[4:0];retire(seq16,0,0,1);end
                            6:begin gpr[ryg]<=ryv>>rxv[4:0];retire(seq16,0,0,1);end
                            7:begin gpr[ryg]<=$signed(ryv)>>>rxv[4:0];retire(seq16,0,0,1);end
                            10:begin gpr[24]<=rxv^ryv;retire(seq16,0,0,1);end
                            11:begin gpr[rxg]<=-ryv;retire(seq16,0,0,1);end
                            12:begin gpr[rxg]<=rxv&ryv;retire(seq16,0,0,1);end
                            13:begin gpr[rxg]<=rxv|ryv;retire(seq16,0,0,1);end
                            14:begin gpr[rxg]<=rxv^ryv;retire(seq16,0,0,1);end
                            15:begin gpr[rxg]<=~ryv;retire(seq16,0,0,1);end
                            16,18:begin
                              if(ry!=0)halt(8'h32);
                              else begin gpr[rxg]<=m16[1] ? lo : hi;retire(seq16,0,0,1);end
                            end
                            17:begin
                              case(ry)
                                0:gpr[rxg]<={24'd0,rxv[7:0]};
                                1:gpr[rxg]<={16'd0,rxv[15:0]};
                                4:gpr[rxg]<={{24{rxv[7]}},rxv[7:0]};
                                5:gpr[rxg]<={{16{rxv[15]}},rxv[15:0]};
                                default:halt(8'h32);
                              endcase
                              if(ry==0 || ry==1 || ry==4 || ry==5)retire(seq16,0,0,1);
                            end
                            24,25,26,27:start_arithmetic(m16[1:0],rxv,ryv);
                            default:halt(8'h32);
                          endcase
                        end
                        30:begin
                          if(m16_extended || branch_pending)halt(8'h35);
                          else begin extend_prefix<=m16;request_second(S_M16_EXTEND);end
                        end
'''+s[end:]
s=s.replace('end else begin\n                        if(load_dest!=0)gpr[load_dest]<=extract_ddr', '''end else if(bus_kind==K_HALF)begin
                        second_word<=extract_ddr(read_latch,bus_virtual[2:0],2,0);
                        state<=second_next_state;
                    end else begin
                        if(load_dest!=0)gpr[load_dest]<=extract_ddr''')
s=s.replace('(pc[1] ? rom_q[31:16] : rom_q[15:0])', 'second_half')
s=s.replace('                S_HALT:begin end', '''                S_M16_EXTEND:begin
                    extend_suffix<=second_half;m16_extended<=1;
                    instruction<={extend_prefix,second_half};state<=S_EXEC;
                end
                S_MULDIV:if(mul_done)begin
                    if(mul_error)halt(8'h36);
                    else begin hi<=mul_hi;lo<=mul_lo;retire(mips16?seq16:seq32,0,0,0);end
                end
                S_HALT:begin end''')
p.write_text(s)
q=Path('files.qip');q.write_text('set_global_assignment -name SYSTEMVERILOG_FILE rtl/pace_muldiv.sv\n'+q.read_text())
q=Path('tools/run_sim.ps1');s=q.read_text().replace("@('rtl/pace_firmware_cpu.sv','rtl/pace_bootrom.sv')", "@('rtl/pace_firmware_cpu.sv','rtl/pace_bootrom.sv','rtl/pace_muldiv.sv')");q.write_text(s)
