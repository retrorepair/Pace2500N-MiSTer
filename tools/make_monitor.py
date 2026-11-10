#!/usr/bin/env python3
"""Generate MONITOR-only tile maps, never invented Sky Guide artwork."""
from pathlib import Path
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--version',default='0.4.6')
parser.add_argument('--experimental',action='store_true')
parser.add_argument('--output',type=Path)
args=parser.parse_args()
R=Path(__file__).resolve().parent.parent/'rom'
W,H=76,32

def page(lines):
    grid=[[' ']*W for _ in range(H)]
    for row,text in lines.items():
        for col,ch in enumerate(text[:W]):grid[row][col]=ch
    return bytes(ord(c) if ord(c)<128 else 32 for row in grid for c in row)

monitor={
 0:' PACE 2500N / NEC EMMA                           FIRMWARE BOOT MONITOR',
 1:' ------------------------------------------------------------------------------',
 2:' GENUINE PACE U202 BOOTLOADER / EXECUTABLE CODE - NOT A DRAWN SKY GUIDE',
 3:' PAL RGB: 625 LINES / 50 FIELDS / SECOND / 576 INTERLACED ACTIVE LINES',
 5:' LIVE CPU STATE                                            HEX VALUES',
 7:'      PROGRAM COUNTER              ',
 8:'      INSTRUCTION WORD             ',
 9:'      INSTRUCTIONS RETIRED         ',
10:'      DDR3 RAM STORES              ',
11:'      LAST RAM STORE ADDRESS       ',
12:'      LAST EMMA WRITE ADDRESS      ',
13:'      LAST EMMA WRITE DATA         ',
14:'      EMMA REGISTER WRITES         ',
15:'      LAST EMMA READ ADDRESS       ',
16:'      GUESSED REGISTER READS       ',
17:'      CPU INSTRUCTION MODE         ',
18:'      HALT REASON CODE             ',
19:'      FULL 2MB U202 LOADED         ',
20:'      UNKNOWN READ POLICY          ',
21:'      TIMER INTERRUPTS             ',
22:' HALT 03 = UNKNOWN MMIO READ       HALT 04 = NEED FULL FLASH',
23:' HALT 10/20/30 = UNKNOWN OPCODE    HALT 05/08 = UNMAPPED ADDRESS',
24:' HALT 06 = UNALIGNED ACCESS        HALT 00 = EXECUTING',
26:' ROM PRELOADED: REAL U202 128 KIB BOOT SECTOR   0xBFC00000 - 0xBFC1FFFF',
27:' NO VERIFIED NEC PERIPHERALS, SMARTCARD, DVB DEMUX OR OPEN-TV VIDEO YET.',
29:' F12: LOAD FULL U202 / RESTART / SELECT UNKNOWN-REGISTER RESPONSE',
31:f' RESEARCH BUILD {args.version}: REAL FIRMWARE BOOT ATTEMPT / SINGLE M10K ROM.'
}
if args.experimental:
    monitor[0]=' PACE 2500N EXPERIMENTAL                         LIVE FIRMWARE MONITOR'
    monitor[2]=' GUESSED MMIO: ZERO + B0009120 BIT 5 / APPROXIMATE 50 MHZ CPU COUNT'
    monitor[31]=f' EXPERIMENTAL {args.version}: PERIPHERAL RESPONSES UNVERIFIED / REAL U202 CODE'
output=args.output or R/'monitor.hex'
output.write_text('\n'.join(f'{c:02X}' for c in page(monitor))+'\n')
print(output,len(page(monitor)))

