"""Explicit standalone application-entry experiment, NOT loader-to-app boot.

Starts an empty CPU/RAM at the original image's reset-style entry stub. It
does not claim that the protected loader hands control over. Optional diagnostic
firmware patches must be explicitly selected and are recorded in the report.
"""
import argparse,gzip,pickle,json
from pathlib import Path
from pace_probe_application_i2c import ApplicationI2CProbe
from pace_lsi_grouped import LsiGroupedDevice,LsiObserved512Device
from pace_probe_graphics import GraphicsProbe
from pace_eeprom import BlankEeprom16
from pace_probe_native_serial import NativeSerialProbe
from pace_diagnostic_gates import apply_diagnostic_sky_gates,apply_diagnostic_root_ready

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--steps',type=int,default=3000000)
    ap.add_argument('--out',default='re/application_entry_01')
    ap.add_argument('--unsafe-zero-mmio',action='store_true')
    ap.add_argument('--experimental-read',action='append',default=[],metavar='ADDRESS=VALUE')
    ap.add_argument('--snapshot',help='Resume this diagnostic entry experiment')
    ap.add_argument('--complete-pending-request',action='store_true',help='Reprocess last previously unsupported peripheral packet with the current profile')
    ap.add_argument('--ack-only54',action='store_true',help='Transport ACK control for command54; supplies no device data')
    ap.add_argument('--transport-ack-unknown',action='store_true',help='Diagnostic packet-receipt ACKs only for unknown commands; no device data')
    ap.add_argument('--i2c-channel0',action='store_true',help='Inferred I2C byte completion/IRQ; default no slave ACK')
    ap.add_argument('--i2c-ack-ca',action='store_true',help='Explicit write-only ACK profile for observed addressCA; no read data')
    ap.add_argument('--i2c-nack-unknown',action='store_true',help='Explicit absent-device NACK control for other I2C addresses')
    ap.add_argument('--i2c-ack-18',action='store_true',help='Address18/19 transport ACK control; still stops before any external read data')
    ap.add_argument('--i2c-register-seed',action='append',default=[],metavar='REGISTER=BYTE',help='Explicit experimental initial device18 value; unseeded/unwritten reads still stop')
    ap.add_argument('--lsi-grouped',action='store_true',help='Strict LSI-family grouped interface; stops on unsupported silicon variant control')
    ap.add_argument('--lsi-observed-512',action='store_true',help='Observed512-word derivative, functional no-RF profile; no acquisition microcode execution')
    ap.add_argument('--complete-pending-graphics',action='store_true',help='Complete the guest DMA12 command already queued in an older snapshot')
    ap.add_argument('--eeprom-blank',action='store_true',help='Diagnostic A0/A1 erased64KiB EEPROM; no original board dump')
    ap.add_argument('--progress-every',type=int,default=0,help='Print progress every this many emulated instructions')
    ap.add_argument('--native-serial0',action='store_true',help='Inferred on-chip TX50/IRQ60/enable70 port; no RX peer data')
    ap.add_argument('--complete-pending-serial0',action='store_true',help='Reattach the original queued TX from a pre-model snapshot')
    ap.add_argument('--fast-crc',action='store_true',help='Exact-code-guarded CRC acceleration, bounded by IRQ/peripheral deadlines')
    ap.add_argument('--graphics-capture-unknown',action='store_true',help='RE ONLY: acknowledge/record unsupported packets without executing pixel operations; output pixels invalid')
    ap.add_argument('--lsi-extended-status-zero',action='store_true',help='Diagnostic no-RF zeros for derivative status APR24..33; silicon values unconfirmed')
    ap.add_argument('--remote-key',type=lambda s:int(s,16),help='Inject one decoded remote key through genuine serial RX path (CC=Guide,80=Sky,0C=Power)')
    ap.add_argument('--compact-history',action='store_true',help='Retain last4096 mode transitions in output; CPU/peripheral state and cumulative counters remain intact')
    ap.add_argument('--diagnostic-sky-gates',action='store_true',help='RE ONLY: patch two presentation decisions in initialized RAM/in-memory U202; not hardware emulation or a solved boot')
    ap.add_argument('--diagnostic-sky-native-only',action='store_true',help='RE ONLY: apply only the RAM default-return patch; leave U202 CRC input unchanged')
    ap.add_argument('--diagnostic-sky-root-ready',action='store_true',help='RE ONLY: force bound root readiness in RAM, alternative to changing its flash initializer')
    ap.add_argument('--stop-before-pc',type=lambda s:int(s,16),help='Save a diagnostic checkpoint before a CPU instruction; cleared on next invocation')
    a=ap.parse_args()
    if a.snapshot:
        with gzip.open(a.snapshot,'rb') as f:old=pickle.load(f)
        assert getattr(old,'entrypoint_experiment',False),'Only resume entry-point diagnostic snapshots'
        p=NativeSerialProbe(old.flash);p.__dict__.update(old.__dict__)
    else:
        p=NativeSerialProbe(Path('firmware/FLASH_U202.bin').read_bytes(),
            unsafe_zero_mmio=a.unsafe_zero_mmio,counter_ticks=8,fast_idle=True)
        p.pc=0xbfc2002c;p.mode16=False
        p.entrypoint_experiment=True
    if a.unsafe_zero_mmio:p.unsafe_zero_mmio=True
    p.stop_before_application_pc=a.stop_before_pc
    p.read_overrides.update({int(k,16):int(v,16) for k,v in (s.split('=') for s in a.experimental_read)})
    if a.ack_only54:p.ack_only54=True
    if a.transport_ack_unknown:p.transport_ack_unknown=True
    if a.i2c_channel0:p.i2c_enabled=True
    if a.i2c_ack_ca:
        assert p.i2c_enabled,'Select --i2c-channel0 explicitly'
        p.i2c_ack_ca=True
    if a.i2c_nack_unknown:
        assert p.i2c_enabled,'Select --i2c-channel0 explicitly'
        p.i2c_nack_unknown=True
    if a.i2c_ack_18:
        assert p.i2c_enabled,'Select --i2c-channel0 explicitly'
        p.i2c_ack_18=True
    if a.eeprom_blank:
        assert p.i2c_enabled and getattr(p,'eeprom',None) is None
        p.eeprom=BlankEeprom16()
    if a.native_serial0:p.serial0_enabled=True
    if a.fast_crc:p.fast_crc=True
    if a.graphics_capture_unknown:p.graphics_capture_unknown=True
    if a.lsi_extended_status_zero:
        assert isinstance(p.lsi_grouped,LsiObserved512Device)
        p.lsi_grouped.extended_status_zero=True
    assert not (a.diagnostic_sky_gates and a.diagnostic_sky_native_only)
    if a.diagnostic_sky_gates or a.diagnostic_sky_native_only:
        assert a.snapshot, 'Select an initialized application diagnostic snapshot explicitly'
        apply_diagnostic_sky_gates(p,native_only=a.diagnostic_sky_native_only)
    if a.diagnostic_sky_root_ready:
        assert a.snapshot and not a.diagnostic_sky_gates
        apply_diagnostic_root_ready(p)
    if a.remote_key is not None:
        assert 0<=a.remote_key<=255
        p.queue_remote_key(a.remote_key)
    if a.complete_pending_serial0:
        assert p.serial0_enabled and a.snapshot
        p.attach_pending_serial0()
    if a.lsi_grouped:
        assert p.i2c_ack_18 and not a.i2c_register_seed,'Select address18 and omit generic register seeds'
        p.lsi_grouped=LsiGroupedDevice()
    if a.lsi_observed_512:
        assert p.i2c_ack_18 and not a.i2c_register_seed and not a.lsi_grouped
        p.lsi_grouped=LsiObserved512Device()
    for item in a.i2c_register_seed:
        assert p.i2c_ack_18,'Select --i2c-ack-18 explicitly'
        key,value=(int(s,16) for s in item.split('='))
        assert 0<=key<=255 and 0<=value<=255
        p.device18_registers[key]=value;p.device18_seeds[key]=value
    if a.complete_pending_request:
        assert a.snapshot and old.status.startswith('Peripheral-data semantics unknown'),old.status
        body=bytes.fromhex(p.peer_requests.pop());p.handle_request(body)
        p.attach_current_request()
    if a.complete_pending_graphics:
        assert not old.status.startswith('Unmodelled graphics'),'Resume the faulting write normally; it has not retired'
        assert p.demux_regs.get(0xb0009010,0)&0x1000
        p.start_graphics_dma()
    p.status='step limit'
    if a.progress_every:
        assert a.progress_every>0
        while p.steps<a.steps:
            p.run(min(a.steps,p.steps+a.progress_every))
            print(f'{p.steps:,} PC {p.pc:08X} | {p.status} | GPU {p.graphics_dma_completions}/{p.graphics_dma_acks} | I2C {len(p.i2c_transactions)} | EEPROM {p.eeprom.read_count if p.eeprom else 0}R/{p.eeprom.write_count if p.eeprom else 0}W',flush=True)
            if p.status!='step limit':break
    else:p.run(a.steps)
    if a.compact_history and len(p.mode_switches)>4096:
        p.mode_switches_omitted=getattr(p,'mode_switches_omitted',0)+len(p.mode_switches)-4096
        p.mode_switches=p.mode_switches[-4096:]
    r=p.report();r['entrypoint_experiment']=dict(start='BFC2002C',empty_initial_ram=True,
        loader_handoff_observed=False,firmware_modified=bool(getattr(p,'diagnostic_firmware_patches',[])),
        host_firmware_patches=getattr(p,'diagnostic_firmware_patches',[]),
        patch_source=getattr(p,'diagnostic_patch_source',None))
    Path(a.out+'.json').write_text(json.dumps(r,indent=2)+'\n')
    Path(a.out+'_ram.bin').write_bytes(p.ram)
    Path(a.out+'.txt').write_bytes(p.uart_tx)
    with gzip.open(a.out+'.pkl.gz','wb') as f:pickle.dump(p,f)
    print('STANDALONE ENTRY EXPERIMENT:',p.steps,p.status,f'PC {p.pc:08X}',repr(p.uart_tx.decode('latin1')))
