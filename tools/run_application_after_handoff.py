"""Application start-up continued from the GENUINE loader handoff (warm reset after command 0x12).

Input: a snapshot from tools/run_warm_reset_handoff.py, taken after the unmodified loader
called the application entry (BFC2048C) on its second boot. The CPU state (GPRs, HI/LO, PC,
ISA mode, CP0) and the whole RAM carry over unchanged; the on-chip peripheral models start at
their reset values and the application programs them itself.

Peripheral profile: the SAME declared approximations as the earlier standalone entry
experiment's 120M snapshot (re/application_serial0_02): unsafe zero MMIO, its explicit read
overrides, I2C channel 0 with CA write ACK / absent-device NACK / address 18 transport ACK, the
observed 512-word LSI no-RF profile, native serial0, transport ACKs for unknown commands and
command 54, counter_ticks 8. EEPROM: --eeprom-file loads a 64 KiB image (e.g. the MiSTer's
EEPROM.bin); default is the blank (erased) diagnostic EEPROM. Nothing in RAM or flash is
patched; the two RAM interventions of the old Guide checkpoint are NOT applied.
"""
import argparse, gzip, json, pickle
from pathlib import Path
from pace_probe_native_serial import NativeSerialProbe
from pace_lsi_grouped import LsiObserved512Device
from pace_eeprom import BlankEeprom16

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--handoff', default='re/warm_reset_handoff_01.pkl.gz')
ap.add_argument('--profile', default='re/application_serial0_02.pkl.gz',
                help='snapshot whose declared peripheral profile (flags, read overrides) is reused')
ap.add_argument('--snapshot', help='resume a snapshot of this run instead')
ap.add_argument('--eeprom-file', help='64 KiB EEPROM image to start from (default: erased)')
ap.add_argument('--lsi-extended-status-zero', action='store_true')
ap.add_argument('--remote-key', type=lambda s: int(s, 16))
ap.add_argument('--steps', type=int, default=50_000_000)
ap.add_argument('--progress-every', type=int, default=5_000_000)
ap.add_argument('--out', default='re/app_after_handoff_01')
a = ap.parse_args()

if a.snapshot:
    with gzip.open(a.snapshot, 'rb') as f:
        old = pickle.load(f)
    p = NativeSerialProbe(old.flash)
    p.__dict__.update(old.__dict__)
else:
    with gzip.open(a.handoff, 'rb') as f:
        h = pickle.load(f)
    assert h.application_entries, 'handoff snapshot has not entered the application'
    with gzip.open(a.profile, 'rb') as f:
        prof = pickle.load(f)
    p = NativeSerialProbe(h.flash, unsafe_zero_mmio=prof.unsafe_zero_mmio, counter_ticks=prof.counter_ticks,
                          fast_idle=True)
    p.read_overrides.update(prof.read_overrides)      # as run_application_entry.py applies them
    for k in ('i2c_enabled', 'i2c_ack_ca', 'i2c_nack_unknown', 'i2c_ack_18', 'transport_ack_unknown',
              'ack_only54', 'serial0_enabled'):
        setattr(p, k, getattr(prof, k))
    p.lsi_grouped = LsiObserved512Device()
    p.eeprom = BlankEeprom16()
    if a.eeprom_file:
        image = Path(a.eeprom_file).read_bytes()
        assert len(image) == 65536
        p.eeprom.data[:] = image
    # the CPU and RAM as the genuine loader left them
    for k in ('r', 'pc', 'mode16', 'hi', 'lo', 'llbit', 'branch', 'steps'):
        setattr(p, k, getattr(h, k))
    p.cp0 = dict(h.cp0)
    p.ram[:] = h.ram
    p.genuine_handoff = dict(snapshot=a.handoff, entered=h.application_entries, eeprom_file=a.eeprom_file)
p.fast_crc = True
if a.lsi_extended_status_zero:
    p.lsi_grouped.extended_status_zero = True
if a.remote_key is not None:
    p.queue_remote_key(a.remote_key)
p.status = 'step limit'
target = p.steps + a.steps
while p.steps < target and p.status == 'step limit':
    p.run(min(target, p.steps + a.progress_every))
    print(f'{p.steps:,} PC {p.pc:08X} | {p.status} | GPU {p.graphics_dma_completions}/{p.graphics_dma_acks} '
          f'| I2C {len(p.i2c_transactions)} | EEPROM {p.eeprom.read_count}R/{p.eeprom.write_count}W', flush=True)
if len(p.mode_switches) > 4096:
    p.mode_switches = p.mode_switches[-4096:]
r = p.report()
r['genuine_handoff'] = p.genuine_handoff
r['firmware_modified'] = False
Path(a.out + '.json').write_text(json.dumps(r, indent=2) + '\n')
Path(a.out + '.txt').write_bytes(bytes(p.uart_tx))
with gzip.open(a.out + '.pkl.gz', 'wb') as f:
    pickle.dump(p, f)
print('DONE', p.steps, p.status, f'PC {p.pc:08X}')
