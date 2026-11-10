# First strict MMIO read: corrected evidence

Ghidra 12.1.4, `MIPS:BE:32:default`, image base `BFC00000`, MIPS16
`ISA_MODE=1` from `BFC01E18`. Reproducible Java script and project are retained.

The original Python and HDL agreed because both used the same wrong PC-relative
base. They selected literal `BFC01E8C` (RAM pointer `80008204`, value `B0000000`).
The instruction at `BFC01E18` is LW v1,0x70(pc). Correct base is `BFC01E18`,
so the literal address is `BFC01E88`, containing `80008200`. Real initialization
puts `B0000010` there. The LHU at `BFC01E1C` therefore reads `B0000012`.

The routine shifts right five, masks bit zero, and returns `0x51` for a clear
bit or `0x36` for a set bit. The MIPS32 caller branches on those results and
writes `0x00232323` or `0x001A1A1A` respectively at its `s0+0x10` address.
No register name, board strap, oscillator or frequency meaning is established.

Primary instruction specification: MIPS Technologies **MD00076 rev 2.50**,
table 3-14, printed page 31 (PDF page 39):
[MIPS16e architecture manual, mirrored original PDF](https://www.0x04.net/~mwk/doc/mips/MD00076-2B-MIPS1632-AFP-02.50.pdf).
It specifies the instruction address outside a delay slot, JR/JALR origin
inside their slot, and first JAL/JALX halfword address inside their slot.
The RTL now retains `branch_pc`; the Python probe passes the origin through
recursive delay-slot execution. Extended instructions remain unsupported.

Validation: `sim/tb_m16_pc.sv` and `tools/test_probe_pc.py` use independent
literal values to distinguish correct bases from PC+4 and from the slot PC.
Strict probe and HDL still stop at `BFC01E1C` with the same instruction counts,
but now identify `B0000012`. This supersedes the handoff's older register trace.
