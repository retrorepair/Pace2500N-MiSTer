"""Seal a frozen candidate build with sources, tests and hardware evidence."""
from pathlib import Path
import argparse,hashlib,json,zipfile
p=argparse.ArgumentParser();p.add_argument('version');args=p.parse_args()
root=Path(__file__).resolve().parents[1];build=root/'builds'/args.version
log=root/f'compile_{args.version}.log'
assert 'Full Compilation was successful' in log.read_text(errors='replace')
archive=root.parent/f'Pace2500N_{args.version}_sources_rbf.zip'
if archive.exists():raise SystemExit('Preserve existing archive')
files={}
for directory in ('rtl','rom','sys'):
    for f in (build/directory).rglob('*'):
        if f.is_file():files[f.relative_to(build).as_posix()]=f
for f in build.iterdir():
    if f.suffix in ('.qpf','.qsf','.qip','.sdc'):files[f.name]=f
for directory in ('tools','firmware'):
    for f in (root/directory).rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:files[f.relative_to(root).as_posix()]=f
for f in root.iterdir():
    if f.suffix in ('.md','.txt','.bat','.mgl') or f.name=='LICENSE':files[f.name]=f
for directory,extensions in (('sim',{'.sv','.svh','.log'}),('re',{'.md','.txt'}),('re/scripts',{'.java'}),('re/deployment',{'.log','.png'})):
    for f in (root/directory).iterdir():
        if f.is_file() and f.suffix in extensions:files[f.relative_to(root).as_posix()]=f
for name in ('oracle_cases.json','oracle_results.json','oracle_comparison.json'):
    files['re/'+name]=root/'re'/name
for f in (build/'output_files').iterdir():
    if f.suffix in ('.rbf','.rpt','.summary'):files['output_files/'+f.name]=f
files[log.name]=log
manifest={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in sorted(files.items())}
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name,f in sorted(files.items()):z.write(f,'Pace2500N/'+name)
    z.writestr('Pace2500N/BUILD_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(sha+'  '+archive.name+'\n')
print(archive,sha,len(files),'files')
