"""Decode the guest's I2C transactions from a tb_sys register log (+mlog), the way
rtl/pace_guide_peripherals.sv interprets the EMMA I2C block: B2006000 = 0x9A starts a
transaction (the next B2006040 write is the device address), 0xA8/0xAC reads a byte (returned in
B2006040). Prints one line per transaction: time, device, bytes written / read.
Usage: i2c_from_mlog.py MLOG [--device HEX]"""
import sys
path = sys.argv[1]
only = int(sys.argv[sys.argv.index('--device') + 1], 16) if '--device' in sys.argv else None
cur = None
def flush():
    if cur and (only is None or cur['dev'] == only):
        print('%10s us  dev %02x  w %s%s' % (cur['t'], cur['dev'], ' '.join(cur['w']),
              ('  r ' + ' '.join(cur['r'])) if cur['r'] else ''))
pending_read = False
for line in open(path):
    f = line.split()
    if len(f) < 5 or not f[3].startswith('b2006'):
        continue
    t, rw, addr, val = f[0], f[2], f[3], int(f[5] if len(f) > 5 else f[4], 16)
    if rw == 'W' and addr == 'b2006000':
        if val == 0x9a:
            flush(); cur = {'t': t, 'dev': None, 'w': [], 'r': []}
        elif val in (0xa8, 0xac):
            pending_read = True
    elif addr == 'b2006040' and cur is not None:
        if rw == 'W':
            if cur['dev'] is None: cur['dev'] = val & 0xff
            else: cur['w'].append('%02x' % (val & 0xff))
        elif pending_read:
            cur['r'].append('%02x' % (val & 0xff)); pending_read = False
flush()
