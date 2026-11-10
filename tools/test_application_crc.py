"""Compare full guest CRC loop execution and exact acceleration, including deadlines."""
from pathlib import Path
import random
from pace_probe_native_serial import NativeSerialProbe
flash=Path('firmware/FLASH_U202.bin').read_bytes();image=Path('re/application_initialized_segments.bin').read_bytes()
for source in (0x80300000,0xbf820024,0x9fa20024):
 for timed in (False,True,'masked_pending','periodic_masked_sources'):
    probes=[]
    for fast in (False,True):
        p=NativeSerialProbe(flash,fast_crc=fast,counter_ticks=8,fast_idle=False)
        p.ram[:len(image)]=image;p.pc=0x800b1b0e;p.mode16=True;p.r[3]=0x12345678
        p.r[4]=source;p.r[5]=10000
        p.ram[0x300000:0x302710]=random.Random(1616).randbytes(10000)
        if timed:
            p.timer_armed=True;p.cp0[9]=0;p.cp0[11]=10000
            p.timer_regs[0xb000d030]=1;p.timer_regs[0xb000d050]=640000;p.timer_remaining=640000
            if timed=='masked_pending':p.cp0[12]=0x10008c00;p.cp0[13]=0x8400;p.timer_pending=True
            if timed=='periodic_masked_sources':
                p.cp0[12]=0x10000001;p.cp0[13]=0x8400;p.timer_pending=True;p.timer_regs[0xb000d020]=1
        p.run(100003);probes.append(p)
    a,b=probes
    for key in ('r','ram','cp0','pc','steps','mode16','hi','lo','mips16_count','extended_count','visits','timer_regs','timer_remaining','timer_pending','expirations','acknowledgements','interrupt_count'):
        assert getattr(a,key)==getattr(b,key),(timed,key)
    assert b.crc_skipped_instructions>0
print('PASS: application CRC100003 instructions on RAM and both NOR aliases, all GPR/RAM/CP0/HI/LO/PC/timer/IRQ state and instruction visits agree across four deadline profiles')
