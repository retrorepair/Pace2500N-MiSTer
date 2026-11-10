"""Opt-in host interventions for studying Sky's presentation path.

These are firmware patches, NOT a hardware model or a solved boot. Addresses
were published by Dan Dunford's GPL-2.0 GoRetroTv, revision fa3a471, and the
native default-return literal was independently checked with Ghidra here.
No original ROM file is written. Both aliases of the in-memory U202 change.
"""
from hashlib import sha256

ORIGINAL_U202 = '32f6b2e84d0c4c4ec280a72f2d080e4b6fa5e68e8438ef712f34f97f63d38c7f'

def apply_diagnostic_sky_gates(p, native_only=False):
    assert p.entrypoint_experiment, 'Never apply to a protected-loader run'
    patches = list(getattr(p, 'diagnostic_firmware_patches', []))
    done = {v['address'] for v in patches}
    image = bytearray(p.flash)
    if '9FC72FA1' in done:
        assert image[0x72fa1] == 0x76
        image[0x72fa1] = 0x75
    assert sha256(image).hexdigest() == ORIGINAL_U202, 'Unexpected U202 image'
    assert p.nor[0].data == p.flash, 'U202 aliases differ'
    if '80054F84' not in done:
        assert p.ram[0x54f84:0x54f88] == b'\xff' * 4, 'Native default not initialized'
        p.ram[0x54f84:0x54f88] = bytes(4)
        patches.append(dict(step=p.steps, address='80054F84', space='RAM', old='FFFFFFFF', new='00000000',
                            purpose='Change AV selection native default return'))
    if not native_only and '9FC72FA1' not in done:
        image[0x72fa1] = 0x76
        p.flash = bytes(image)
        p.nor[0].data = p.flash
        patches.append(dict(step=p.steps, address='9FC72FA1', space='U202 in-memory aliases', old='75', new='76',
                            purpose='Change Ocode presentation gate constant'))
    p.diagnostic_firmware_patches = patches
    p.diagnostic_patch_source = 'https://github.com/ddunford/GoRetroTv/tree/fa3a471df9c273f4f62ecbcc6a566f3c6e871dd4'
    p.diagnostic_original_u202_sha256 = ORIGINAL_U202

def apply_diagnostic_root_ready(p):
    """Alternative to the flash patch: set the existing root object's ready field.

    This is the reference's earlier two-RAM-word experiment. It must be named
    separately because patching the flash initializer after it ran has no effect.
    """
    assert p.entrypoint_experiment
    assert sha256(p.flash).hexdigest() == ORIGINAL_U202, 'Use the RAM-only experiment'
    assert p.ram[0x54f84:0x54f88] == bytes(4), 'Apply the native gate before startup'
    table=int.from_bytes(p.ram[0x105e9c:0x105ea0],'big')&0x1fffffff
    assert 0x100000 <= table < len(p.ram)-200
    root=int.from_bytes(p.ram[table+196:table+200],'big')
    offset=root&0x1fffffff
    assert root&0xe0000000==0x80000000 and 0x100000<=offset<len(p.ram)-64
    address=offset+0x14
    assert p.ram[address:address+4]==bytes(4), 'Unexpected root readiness value'
    p.ram[address:address+4]=(1).to_bytes(4,'big')
    p.diagnostic_firmware_patches.append(dict(step=p.steps,address=f'{0x80000000+address:08X}',
        space='RAM application object',old='00000000',new='00000001',
        purpose='Host-forced presentation readiness; NOT a peripheral response'))
