#!/usr/bin/env python3
"""Build project sources from the public MiSTer Killer Instinct shell.
This intentionally reuses only the upstream sys/ hardware abstraction and
Cyclone V board pinout; the KI MIPS CPU is NOT yet instantiated.
"""
import argparse, zipfile, shutil, urllib.request, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
UPSTREAM='https://github.com/MiSTer-devel/Arcade-KillerInstinct_MiSTer/archive/refs/heads/main.zip'
p=argparse.ArgumentParser();p.add_argument('--ki',type=Path,help='Path to extracted Arcade-KillerInstinct_MiSTer repository');p.add_argument('--download',action='store_true',help='Download the public KI repo if no --ki is specified');args=p.parse_args()
if args.ki: ki=args.ki.resolve()
elif (ROOT/'tools'/'mister_platform.qsf').exists() and (ROOT/'sys'/'sys_top.v').exists() and not args.download:
    ki=None # Reuse the bundled, hashed platform shell without network access.
elif args.download:
    target=ROOT/'reference'/'Arcade-KillerInstinct_MiSTer';target.parent.mkdir(exist_ok=True)
    if not (target/'KillerInstinct.qsf').exists():
        print('Downloading MiSTer platform sources:',UPSTREAM)
        with tempfile.TemporaryDirectory() as tmp:
            fn=Path(tmp)/'ki.zip';urllib.request.urlretrieve(UPSTREAM,fn)
            with zipfile.ZipFile(fn) as z:z.extractall(tmp)
            matches=list(Path(tmp).glob('Arcade-KillerInstinct_MiSTer-*'))
            if not matches:raise SystemExit('Unexpected GitHub archive structure')
            shutil.copytree(matches[0],target,dirs_exist_ok=True)
    ki=target
else:
    ki=ROOT/'reference'/'Arcade-KillerInstinct_MiSTer'
if ki is not None and (not (ki/'KillerInstinct.qsf').exists() or not (ki/'sys'/'sys_top.v').exists()):
    raise SystemExit('Missing KI reference repo. Use --download or --ki <path>.')
if not ((ki/'sys' if ki is not None else ROOT/'sys')/'emu_ports.vh').exists(): raise SystemExit('Upstream sys/emu_ports.vh not found')
if ki is not None and not (ROOT/'sys'/'sys_top.v').exists():
    shutil.copytree(ki/'sys', ROOT/'sys', dirs_exist_ok=True)
qsf=(ki/'KillerInstinct.qsf' if ki is not None else ROOT/'tools'/'mister_platform.qsf').read_text()
if 'source files.qip' not in qsf:raise SystemExit('KI QSF changed: source files.qip missing')
qsf=qsf.replace('source files.qip','source files.qip\nset_global_assignment -name SDC_FILE Pace2500N.sdc')
qsf=qsf.replace('set_global_assignment -name LAST_QUARTUS_VERSION "17.0.2 Lite Edition"','set_global_assignment -name LAST_QUARTUS_VERSION "17.0.2 Lite Edition"')
(ROOT/'Pace2500N.qsf').write_text(qsf)
(ROOT/'Pace2500N.qpf').write_text('PROJECT_REVISION = "Pace2500N"\n')
print('Created:',ROOT/'Pace2500N.qpf')
print('MiSTer sys_top and HPS integration from:',ki)
print('Design: U202 executable boot CPU, MiSTer DDR3 memory bridge, 625/50 576i RGB monitor. Not a working Sky Guide.')
print('Open Pace2500N.qpf in Quartus Prime Standard 17.0+ and Compile.')
