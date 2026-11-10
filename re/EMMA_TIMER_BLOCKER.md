# Original scheduler blocker resolved in software

This is genuine U202 execution in a research CPU, not FPGA validation of the
new peripheral model. MiSTer remains on v046 EXP, which has only CP0 timer IRQs.

## Evidence from Ghidra

The original wait is BFC069F0: obtain semaphore8000A820 indefinitely. Its name
is EVTTick. BFC06914 creates EVTHISR at8000A6F8 (entry9FC06EB5) and EVTTask at
8000A750 (entry9FC06EC9), then starts the timer driver.

Driver open at BFC03FA8, control at BFC04210, reload at BFC042EC:

| Register | Observed role |
| --- | --- |
| B000D050 | timer0 reload, programmed000C5C10 |
| B000D030 bit0 | channel0 enable/start |
| B000D020 bit0 | programmed1; periodic behavior inferred |
| B000D0C0 bit0 | local interrupt enable |
| B000D0D0 bit0 | pending status read by handler |
| B000D0E0 bit0 | write-one acknowledgement |
| B0000030 bit6 | aggregated EMMA pending status |
| B0000040 bit6 | aggregated EMMA enable |
| CP0 Cause bit10 (IP2) | external CPU interrupt |

BFC0EE4C dispatches IP2 to BFC01BD4; the latter ANDs EMMA pending and enable,
finds the registered bit mask, and calls its handler. BFC0434C reads D0D0,
acknowledges D0E0, and calls callback9FC06EA1. That activates EVTHISR through
Nucleus. EVTHISR releases EVTTick; EVTTask runs and releases initialization
semaphores. The model never modifies those semaphores or forces guest PC.

Files: device_open_ghidra.txt, device_start_ghidra.txt, device_clock_ghidra.txt,
device_isr_ghidra.txt, irq_dispatch32_ghidra.txt, emma_irq_dispatch_ghidra.txt,
event_hisr_ghidra.txt, event_task_ghidra.txt, emma_timer_decompilation.txt.
Decompiled C has incomplete indirect-return/type recovery; instruction listings
and measured execution take precedence.

## Measured results

`python tools/pace_probe_emma_timer.py --steps 5000000 --out re/emma_timer_02.json`

- Original wait returns success at instruction3671510, PC9FC069F6, v0=0.
- Event initialization succeeds at9FC069FC; BOOTMain creates more tasks.
- Five million instructions:54 timer expirations and54 genuine acknowledgements.
- Eight million instructions:173 expirations/acks;1832 distinct MIPS32 and5824
  distinct MIPS16 instruction addresses (baseline1699/4403).
- A second clock ratio (16 instead of32 peripheral ticks per instruction)
  returns success at3722135 and acknowledges7/7 expirations by4M instructions.
- `python tools/test_emma_timer.py` checks reload, enable, both interrupt gates,
  periodic expiry, acknowledgement and stopping.

Timer clock and periodic bit are inferred. CP0 uses synthetic8 ticks per guest
instruction; other peripherals retain explicit zero guesses plus9120=20.
This demonstrates the missing timer event, not a complete NEC specification.

## Next blocker

BOOTMain now waits at BFC0630C on semaphore8000A6D0, named APeriph. The stack
includes BFC05C9C/BFC062F0. Its request goes through BFC05904 and queued SMT
processing. A send at BFC03E4C fails validation BFC038F0: byte80013CCC is0.

BFC03910 sets that byte and installs callbacks at table80013C88+48/+4C;
it configures the16-channel block B200A000 and registers interrupt bit4. The
only direct caller found is BFC036A6, inside BFC03688. That routine is called
by the BOOTMain path at BFC01312. The current run instead takes the branch at
BFC012C6 because RAM800081F8=1, enters BFC05C6C and reaches APeriph before
that initialization. Why800081F8 is1, and the intended branch semantics,
remain unresolved. Do not force the flag or fabricate a peripheral response.

The B2001000 UART-like block also has unmodelled RX/TX behavior; BFC02904
drains RX or times out. No evidence yet makes that the cause of the GPIO gate.
Next useful RE: provenance of800081F8 and boot path initialization order.
