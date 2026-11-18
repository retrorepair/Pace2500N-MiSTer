"""Loader -> application handoff by a warm reset (the front-panel controller's command 0x12).

Hypothesis from the loader's own code (Ghidra: re/loader_handoff_ghidra.txt,
re/loader_bootmain_ghidra.txt, re/loader_warmboot_ghidra.txt):
  - BOOTMain (BFC012C6) compares a RAM signature with "MIKE PEARCE WOZ HERE"; only when it
    is absent (power-on) does it write it and clear the 0x300-byte block at A0002000.
  - BFC126E4, called before image selection, reads the header kept in that block and, when it
    names an entry and matches the box's manufacturer/version bytes, calls BFC02944, which
    calls the entry: the jump into the application.
  - On a power-on the block is empty, so select_and_handoff validates the images, stores the
    chosen header at A0002000 and calls BFC036F8: front-end setup, then front-panel command
    `03 00 12 00` once, then sleep for ever.
So command 0x12 must make the board reset the CPU with RAM intact; the second boot finds the
header and enters the application.

This run models only that: a fresh probe (every on-chip register, the CPU, timers, demux,
serial and NOR state at their reset values) with the external RAM copied from a snapshot
taken after the loader sent 0x12. Nothing in RAM or flash is edited; no PC is set other than
the reset vector. Same peripheral profile as the snapshot's run.
"""
import argparse, gzip, json, pickle
from pathlib import Path
from pace_probe_boot_peripheral import BootPeripheralProbe

ap = argparse.ArgumentParser()
ap.add_argument('--snapshot', default='re/application_boot_03.pkl.gz')
ap.add_argument('--steps', type=int, default=120_000_000)
ap.add_argument('--chunk', type=int, default=2_000_000)
ap.add_argument('--out', default='re/warm_reset_handoff_01')
a = ap.parse_args()

with gzip.open(a.snapshot, 'rb') as f:
    old = pickle.load(f)
sent_0x12 = [r for r in old.peer_requests if len(r) >= 6 and r[4:6] == '12']
print('snapshot', a.snapshot, 'steps', old.steps, 'front-panel 0x12 requests seen:', len(sent_0x12))
print('header kept at A0002000:', bytes(old.ram[0x2000:0x2020]).hex(' '))

p = BootPeripheralProbe(old.flash, unsafe_zero_mmio=old.unsafe_zero_mmio, counter_ticks=old.counter_ticks,
                        read_overrides=dict(old.read_overrides))
p.fast_idle, p.fast_crc = True, True
p.ram[:] = old.ram                       # external SDRAM keeps its contents through the reset
p.status = 'step limit'
done = 0
while done < a.steps and not p.application_entries and p.status == 'step limit':
    p.run(p.steps + a.chunk)
    done = p.steps
    print(f'{p.steps:>11,} PC {p.pc:08X} {"MIPS16" if p.mode16 else "MIPS32"} console {bytes(p.uart_tx)[-60:]!r}', flush=True)
r = p.report()
r['warm_reset'] = dict(snapshot=a.snapshot, snapshot_steps=old.steps, ram_copied=True, flash_unmodified=True)
Path(a.out + '.json').write_text(json.dumps(r, indent=2) + '\n')
Path(a.out + '.txt').write_bytes(bytes(p.uart_tx))
with gzip.open(a.out + '.pkl.gz', 'wb') as f:
    pickle.dump(p, f)
print('status', p.status, 'APPLICATION ENTRIES', p.application_entries)
