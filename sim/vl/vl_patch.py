#!/usr/bin/env python3
"""Verilator 5.020 cannot take a non-blocking assignment to an array element inside a for
loop (BLKLOOPINIT). Write copies of the RTL files that have one, with those loops written
out; the meaning is unchanged. Usage: vl_patch.py OUTDIR"""
import sys, re
out = sys.argv[1]
s = open('rtl/pace_guide_peripherals.sv').read()
a = "for(n=0;n<128;n=n+1)if(is_hot(n[6:0]))csr[n]<=seed[n];"
b = "for(n=0;n<128;n=n+1)if(is_hot(n[6:0]) && io_index==n[6:0])csr[n]<=io_wdata;"
assert s.count(a) == 1 and s.count(b) == 1
s = s.replace(a, ''.join("if(is_hot(7'd%d))csr[%d]<=seed[%d];" % (i, i, i) for i in range(128)))
s = s.replace(b, "if(io_hot)csr[io_index]<=io_wdata;")   # io_hot = is_hot(io_index)
open(out + '/pace_guide_peripherals.sv', 'w').write(s)

# The old CPU as the shadow in sim/vl/tb_shadow.sv: its own interrupt decision is replaced by
# rp_take (an interrupt where the new CPU took one), and CP0 Count / Cause / Random reads
# return rp_value (the new CPU's value: they depend on time). Nothing else is changed.
s = open('rtl/pace_firmware_cpu.sv').read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
rep("    input wire io_ready, io_irq,\n",
    "    input wire io_ready, io_irq,\n    input wire rp_take, rp_patch,\n    input wire [31:0] rp_cause, rp_value,\n")
rep("                    if(interrupt_pending)begin", "                    if(rp_take)begin")
rep("cp0[13]<=(cause_with_timer&32'h7fffff83) | (delay_slot?32'h80000000:32'd0);",
    "cp0[13]<=(rp_cause&32'h0000ff00) | (delay_slot?32'h80000000:32'd0);")
rep("if(rs==0)begin if(rt!=0)gpr_wr(rt,cp0[rd]);",
    "if(rs==0)begin if(rt!=0)gpr_wr(rt,(rp_patch && (rd==5'd9 || rd==5'd13 || rd==5'd1)) ? rp_value : cp0[rd]);")
rep("for(j=0;j<32;j=j+1) cp0[j]<=0;", ''.join("cp0[%d]<=0;" % i for i in range(32)))
open(out + '/pace_firmware_cpu.sv', 'w').write(s)
