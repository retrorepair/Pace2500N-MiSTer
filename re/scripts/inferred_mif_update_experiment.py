"""Retained one-byte monitor MIF update experiment, not the normal build path.

The first digital capture was incomplete and was initially misdiagnosed as a
ROM failure. A clean full compile produced the identical RBF SHA-256, and a
fresh capture plus CRT photo showed the full monitor. The update itself was
therefore consistent with the normal source build. Normal releases use full
compilation so there is no dependency on editing generated database files.
"""
from pathlib import Path
import re

root=Path(__file__).resolve().parents[1]
data=bytes(int(line,16) for line in (root/'rom/monitor.hex').read_text().splitlines())
assert len(data)==2432
matched=0
for p in (root/'db').glob('Pace2500N.ram*_pace_boot_monitor_*.hdl.mif'):
    text=p.read_text()
    if 'DEPTH=2432;' not in text:
        continue
    assert 'WIDTH=8;' in text and 'ADDRESS_RADIX=UNS;' in text and 'DATA_RADIX=BIN;' in text
    words=re.findall(r'(?m)^\s*(\d+)\s*:\s*([01]{8});',text)
    assert len(words)==len(data) and {int(a) for a,_ in words}==set(range(len(data)))
    changes=sum(data[int(a)]!=int(value,2) for a,value in words)
    def replace(m):
        return m[1]+format(data[int(m[2])],'08b')+';'
    updated=re.sub(r'(?m)^(\s*(\d+)\s*:\s*)[01]{8};',replace,text)
    p.write_text(updated)
    print('Synced',p.name,'changed bytes:',changes)
    matched+=1
assert matched==1,matched
