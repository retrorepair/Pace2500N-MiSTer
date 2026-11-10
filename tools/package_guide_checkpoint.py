"""Seal software Guide evidence, source and resumable states; never overwrite."""
from pathlib import Path
from hashlib import sha256
import json,zipfile
root=Path(__file__).resolve().parents[1]
archive=root.parent/'Pace2500N_RE_GuideDiagnostic_20261108_1933.zip'
assert not archive.exists(), 'Preserve existing checkpoint archive'
files=set()
for directory,pattern in [('tools','*.py'),('re/scripts','*.java'),('firmware','*.bin')]:
    files.update(p for p in (root/directory).glob(pattern) if p.is_file())
files.update([root/'LICENSE',root/'CURRENT_STATUS.md',
    root/'re/GUIDE_DIAGNOSTIC_CHECKPOINT.md',root/'re/APPLICATION_HANDOFF_INVESTIGATION.md',
    root/'re/REFERENCE_GORETROTV.json',root/'re/reference_goretrotv/LICENSE',
    root/'re/application_initialized_segments.bin',root/'re/validation_20261108_guide.json'])
for stem in ['application_presentation_gate','application_window_binding','application_blitter_mode',
             'application_render_driver_init']:
    files.update((root/'re').glob(stem+'*ghidra.txt'))
    files.update((root/'re').glob(stem+'*decompile.txt'))
for stem in ['application_guide_diagnostic_200M','application_all_channels_diagnostic_210M',
             'application_unpatched_blue_237M']:
    files.update((root/'re').glob(stem+'.png*'))
# Minimal original checkpoints required by validation and the staged replay.
for stem in ['application_i2c_ack_01','application_uart_01','application_serial0_02',
             'application_first_gate_checkpoint','application_native_gate_01',
             'application_guide_ramgates_01','application_guide_fault_trace',
             'application_guide_ramgates_03','application_all_channels_01']:
    files.add(root/'re'/(stem+'.pkl.gz'))
for stem in ['application_guide_ramgates_03','application_all_channels_01']:
    for suffix in ['.json','_ram.bin','.txt']:files.add(root/'re'/(stem+suffix))
assert all(p.is_file() for p in files),[str(p) for p in files if not p.is_file()]
manifest={p.relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
assert manifest['firmware/FLASH_U202.bin']=='32f6b2e84d0c4c4ec280a72f2d080e4b6fa5e68e8438ef712f34f97f63d38c7f'
assert manifest['firmware/FLASH_U203.bin']=='7832d619b63e369bdd4a0f3de8dd73c98a99285d96c94a8bb0a39fe829ce1f40'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in manifest:z.write(root/name,'Pace2500N/'+name)
    z.writestr('Pace2500N/GUIDE_CHECKPOINT_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert sha256(z.read('Pace2500N/'+name)).hexdigest()==digest,name
digest=sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n')
print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,files=len(files),sha256=digest,all_archived_hashes_verified=True),indent=2))
