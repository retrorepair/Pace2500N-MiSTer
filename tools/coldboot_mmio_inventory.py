"""Inventory of the device registers a cold boot touches, from the simulator runs, against what
the FPGA core implements. Writes re/COLDBOOT_MMIO_INVENTORY.md.

Runs: loader power-on (re/application_boot_03), loader after the warm reset
(re/warm_reset_handoff_01), application start-up from the handoff (re/app_after_handoff_02).
FPGA coverage is read from the RTL: the checkpoint CSR map (rtl/pace_checkpoint_csr.vh), the
registers pace_guide_peripherals models itself ("hot"), and the address windows other modules
decode (demux B000A, GPU B0009, ...).
"""
import collections, gzip, pickle, re
from pathlib import Path

RUNS = [('loader', 're/application_boot_03.pkl.gz'), ('warm', 're/warm_reset_handoff_01.pkl.gz'),
        ('app', 're/app_after_handoff_02.pkl.gz')]
csr = set(int(a, 16) for a in re.findall(r"32'h([0-9a-f]{8}):csr_index", Path('rtl/pace_checkpoint_csr.vh').read_text()))
per = Path('rtl/pace_guide_peripherals.sv').read_text()
hot = set(int(a, 16) for a in re.findall(r"csr_index\(32'h([0-9a-f]{8})\)", per[per.index('function automatic is_hot'):per.index('endfunction')]))
modelled = set(int(a, 16) for a in re.findall(r"32'h([0-9a-f]{8})", per)) - csr
WINDOWS = [(0xb000a000, 0xb000b000, 'demux (pace_section_demux)'), (0xb0009000, 0xb0009200, 'GPU/blitter'),
           (0xb0000000, 0xb0001000, 'EMMA system'), (0xb4080000, 0xb4080008, 'external 16550 UART'),
           (0xb2002000, 0xb2002100, 'serial0 (front panel link)'), (0xb2006000, 0xb2006100, 'I2C'),
           (0xb2009000, 0xb200a100, 'serial/clock'), (0xb000d000, 0xb000d100, 'EMMA timer')]
counts = collections.defaultdict(lambda: collections.Counter())
overrides = {}
for name, fn in RUNS:
    p = pickle.load(gzip.open(fn, 'rb'))
    for (kind, addr, size), n in p.mmio.items():
        counts[addr][f'{name}_{kind[0]}'] += n
    for a, v in getattr(p, 'read_overrides', {}).items():
        overrides[a] = v
rows = []
for addr in sorted(counts):
    c = counts[addr]
    where = next((w for lo, hi, w in WINDOWS if lo <= addr < hi), 'other')
    fpga = 'modelled' if addr in hot or addr in modelled else 'CSR storage' if addr in csr else '-'
    ov = f'{overrides[addr]:#x}' if addr in overrides else ''
    rows.append(f'| {addr:08X} | {where} | {c["loader_r"]}/{c["loader_w"]} | {c["warm_r"]}/{c["warm_w"]} | '
                f'{c["app_r"]}/{c["app_w"]} | {ov} | {fpga} |')
out = ['# Cold-boot device register inventory', '',
       'Reads/writes per simulator run (loader power-on, loader after warm reset, application start-up '
       'from the handoff). "override" = a declared read value the simulator profile supplies. "FPGA" = '
       'modelled by pace_guide_peripherals, plain CSR storage seeded from the checkpoint, or neither.', '',
       '| address | block | loader r/w | warm r/w | app r/w | override | FPGA |', '|---|---|---|---|---|---|---|'] + rows
Path('re/COLDBOOT_MMIO_INVENTORY.md').write_text('\n'.join(out) + '\n')
none = [r for r in rows if r.endswith('| - |')]
print(len(rows), 'registers;', len(none), 'not handled by the FPGA core at all')
print('\n'.join(none[:60]))
