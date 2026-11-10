"""Package sources, final RBF, reports and selected validation evidence."""
from pathlib import Path
import hashlib
import json
import zipfile

root=Path(__file__).resolve().parents[1]
rbf=root/'output_files/Pace2500N.rbf'
build_log=root/'compile_v044_final.log'
if not build_log.exists() or 'Full Compilation was successful' not in build_log.read_text(errors='replace'):
    raise SystemExit('Final clean full compilation must pass first')
if not rbf.exists() or rbf.stat().st_mtime < max(p.stat().st_mtime for p in (root/'rtl').glob('*.sv')):
    raise SystemExit('A current compiled RBF is required')
files=set()
for p in root.iterdir():
    if p.is_file() and (p.suffix in {'.md','.txt','.qpf','.qsf','.qip','.sdc','.bat','.mgl'} or p.name=='LICENSE'):
        files.add(p)
for directory in ('firmware','rom','rtl','sys','tools'):
    files.update(p for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
files.update(p for p in (root/'sim').iterdir() if p.suffix in {'.sv','.log'} and p.is_file())
files.update(p for p in (root/'re').iterdir() if p.suffix in {'.md','.txt'} and p.is_file())
files.update((root/'re/scripts').glob('*.java'))
files.update((root/'output_files').glob('*.rpt'))
files.update((root/'output_files').glob('*.summary'))
files.add(rbf)
for name in ('compile_v044_final.log','sim/probe_strict_corrected.json',
             're/deployment/uart_v044_verified.log','re/deployment/ddr_v044_verified.log',
             're/deployment/boot_monitor_v044.png'):
    p=root/name
    if p.exists(): files.add(p)
files=sorted(files)
manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
archive=root.parent/'Pace2500N_v044_sources_rbf.zip'
if archive.exists():
    raise SystemExit('Preserve the existing verified v0.4.4 archive; choose a new release name for later work')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files: z.write(p,root.name+'/'+p.relative_to(root).as_posix())
    z.writestr(root.name+'/BUILD_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(sha+'  '+archive.name+'\n')
print('Archive:',archive)
print('SHA256:',sha)
print('Files:',len(files),'bytes:',archive.stat().st_size)
