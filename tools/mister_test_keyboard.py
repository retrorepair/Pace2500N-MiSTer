"""MiSTer-only smoke test: ordinary USB-style Linux key events via uinput.

Does not access guest RAM, drive firmware state, or emulate the CPU. Run on
MiSTer with explicit key names to exercise the normal Main->hps_io input path.
"""
import os,fcntl,struct,time,sys
KEYS={'F1':59,'F2':60,'F3':61,'F4':62,'F5':63,'F6':64,'F7':65,'F8':66,'F9':67,
      'F10':68,'ENTER':28,'ESC':1,'UP':103,'DOWN':108,'LEFT':105,'RIGHT':106,
      'R':19,'G':34,'Y':21,'B':48}
fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
try:
    fcntl.ioctl(fd,0x40045564,1)
    for key in KEYS.values():fcntl.ioctl(fd,0x40045565,key)
    fcntl.ioctl(fd,0x40045565,30) # keyboard classification includes letters
    setup=struct.pack('80sHHHHi',b'Pace FPGA keyboard test',3,0x1209,0x2500,1,0)+bytes(1024)
    os.write(fd,setup);fcntl.ioctl(fd,0x5501)
    time.sleep(3)
    def event(kind,code,value):os.write(fd,struct.pack('llHHi',0,0,kind,code,value))
    for name in sys.argv[1:]:
        key=KEYS[name.upper()]
        event(1,key,1);event(0,0,0);time.sleep(.12)
        event(1,key,0);event(0,0,0);print('sent',name,flush=True);time.sleep(3)
finally:
    try:fcntl.ioctl(fd,0x5502)
    except OSError:pass
    os.close(fd)
