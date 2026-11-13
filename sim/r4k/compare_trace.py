#!/usr/bin/env python3
"""Compare the new CPU's retire trace (sim/r4k/tb_r4k.vhd) with the reference
(sim/r4k/tb_ref_trace.sv): same instruction addresses in the same order, and the same
register results. Lines: "index pc mode reg value"; reference "M ..." lines are skipped.
The new CPU reports the highest register that CHANGED, so a reference write of an
unchanged value matches "no register"."""
import sys

def load(path, limit):
    out = []
    with open(path) as f:
        for line in f:
            p = line.split()
            if not p or p[0] == 'M':
                continue
            out.append((int(p[1], 16), int(p[2]), int(p[3]), int(p[4], 16)))
            if len(out) >= limit:
                break
    return out

ref_path, new_path = sys.argv[1], sys.argv[2]
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
first = int(sys.argv[4]) if len(sys.argv) > 4 else 0      # reference index the new run starts at
ref = load(ref_path, first + limit)[first:]
raw = load(new_path, limit * 2 + 8)
# The new CPU carries the MIPS16 mode in pc bit 0 and retires EXTEND / JAL first halves as
# NOPs at the same address as the instruction they prefix: fold those.
raw = [(pc & ~1, m, r, v) for pc, m, r, v in raw]
new = [x for i, x in enumerate(raw) if not (i + 1 < len(raw) and x[2] == 0 and raw[i + 1][0] == x[0])]
# The new CPU's export lags two retirements behind, so its first instruction(s) may not
# appear: align on the first reference instruction it does show.
skip, start = next((k, i) for k in range(4) for i, x in enumerate(new[:8]) if x[0] == ref[k][0])
regs = [0] * 32
if first:
    import os
    st = [int(l, 16) for l in open(os.environ.get('START_STATE', 'sim/r4k/state.hex'))]
    regs = st[:32]
for x in ref[:skip]:
    if x[2]:
        regs[x[2]] = x[3]
ref, new = ref[skip:], new[start:]
n = min(len(ref), len(new))
for i in range(n):
    (rpc, rm, rr, rv), (npc, nm, nr, nv) = ref[i], new[i]
    changed = rr != 0 and regs[rr] != rv
    # (a write of an unchanged value may still show: the new CPU's export mirror starts at zero)
    ok = rpc == npc and ((nr == rr and nv == rv) or (not changed and nr == 0))
    if not ok:
        print(f'MISMATCH at instruction {i}: reference pc {rpc:08x} mode {rm} r{rr}={rv:08x} (changed={changed})'
              f' | new pc {npc:08x} r{nr}={nv:08x}')
        for j in range(max(0, i - 4), min(n, i + 3)):
            print(f'   {j}: ref {ref[j][0]:08x} r{ref[j][2]}={ref[j][3]:08x}   new {new[j][0]:08x} r{new[j][2]}={new[j][3]:08x}')
        sys.exit(1)
    if rr:
        regs[rr] = rv
print(f'MATCH: {n} instructions identical (pc and register results)')
