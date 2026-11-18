# Cold-boot device register inventory

Reads/writes per simulator run (loader power-on, loader after warm reset, application start-up from the handoff). "override" = a declared read value the simulator profile supplies. "FPGA" = modelled by pace_guide_peripherals, plain CSR storage seeded from the checkpoint, or neither.

| address | block | loader r/w | warm r/w | app r/w | override | FPGA |
|---|---|---|---|---|---|---|
| B0000010 | EMMA system | 1/0 | 1/0 | 6/0 | 0x0 | CSR storage |
| B0000012 | EMMA system | 1/0 | 1/0 | 1/0 | 0x0 | - |
| B0000030 | EMMA system | 4053/1 | 142/1 | 44886/1 | 0x0 | CSR storage |
| B0000040 | EMMA system | 4061/9 | 150/9 | 44897/12 | 0x1212446 | modelled |
| B0000050 | EMMA system | 0/1 | 0/1 | 0/1 |  | - |
| B0000060 | EMMA system | 0/1 | 0/1 | 0/1 |  | - |
| B0000230 | EMMA system | 0/1 | 0/1 | 0/2 |  | - |
| B0000400 | EMMA system | 0/1 | 0/2 | 0/0 |  | - |
| B0000410 | EMMA system | 0/1 | 0/2 | 0/0 |  | - |
| B0000430 | EMMA system | 0/1 | 0/2 | 0/0 |  | - |
| B0000440 | EMMA system | 0/1 | 0/2 | 0/0 |  | - |
| B0000600 | EMMA system | 0/4 | 0/5 | 0/2 |  | - |
| B0000610 | EMMA system | 0/4 | 0/5 | 0/3 |  | - |
| B0000620 | EMMA system | 0/3 | 0/3 | 0/3 |  | - |
| B0000800 | EMMA system | 0/1 | 0/1 | 0/1 |  | - |
| B0002000 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0002004 | other | 0/1 | 0/1 | 14/15 |  | CSR storage |
| B0002008 | other | 0/0 | 0/0 | 2/3 |  | CSR storage |
| B0002010 | other | 0/1 | 0/1 | 4/5 |  | CSR storage |
| B0002014 | other | 0/0 | 0/0 | 1/3 |  | CSR storage |
| B000206C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002070 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002074 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002078 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000207C | other | 0/0 | 0/0 | 2/1 |  | CSR storage |
| B0002080 | other | 0/0 | 0/0 | 5/5 |  | CSR storage |
| B0002084 | other | 0/0 | 0/0 | 5/5 |  | CSR storage |
| B0002090 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002094 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002098 | other | 0/0 | 0/0 | 2/1 |  | CSR storage |
| B000209C | other | 0/0 | 0/0 | 2/1 |  | CSR storage |
| B00020A0 | other | 0/0 | 0/0 | 2/1 |  | CSR storage |
| B00020A4 | other | 0/0 | 0/0 | 2/1 |  | CSR storage |
| B00020A8 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00020B0 | other | 240/240 | 240/240 | 0/0 | 0x0 | - |
| B00020B4 | other | 0/8 | 0/8 | 0/0 |  | - |
| B00020B8 | other | 484/0 | 484/0 | 0/0 | 0x0 | - |
| B00020BC | other | 0/8 | 0/8 | 0/0 |  | - |
| B00020C0 | other | 0/0 | 0/0 | 8/16 |  | CSR storage |
| B00020C4 | other | 0/0 | 0/0 | 0/16 |  | - |
| B00020D0 | other | 0/0 | 0/0 | 0/8 |  | - |
| B00020D4 | other | 0/0 | 0/0 | 0/8 |  | - |
| B0002100 | other | 0/1 | 0/1 | 0/0 |  | - |
| B0002104 | other | 0/0 | 0/0 | 1/1 |  | CSR storage |
| B0002110 | other | 0/0 | 0/0 | 0/2 |  | - |
| B000211C | other | 0/0 | 0/0 | 2/2 |  | CSR storage |
| B0002140 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0002144 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002148 | other | 0/0 | 0/0 | 0/3 |  | - |
| B000214C | other | 0/0 | 0/0 | 0/2 |  | - |
| B00021C0 | other | 0/0 | 0/0 | 8/10 |  | CSR storage |
| B00021C4 | other | 0/0 | 0/0 | 0/5 |  | - |
| B00021C8 | other | 0/0 | 0/0 | 0/5 |  | - |
| B00021CC | other | 0/0 | 0/0 | 0/2 |  | - |
| B00021E8 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002248 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002250 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002254 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002258 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002280 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002284 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002288 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000228C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002290 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002294 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002298 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000229C | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022A0 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022A4 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022A8 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022AC | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022B0 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022B4 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022B8 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022BC | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022C0 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022C4 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022C8 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022CC | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022D0 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022D4 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022D8 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022DC | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022E0 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022E4 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022E8 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022EC | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022F0 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022F4 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022F8 | other | 0/0 | 0/0 | 0/1 |  | - |
| B00022FC | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002300 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002304 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002308 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000230C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002310 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002314 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002318 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000231C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002320 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002324 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002328 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000232C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002330 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002334 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002338 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000233C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002340 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002344 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002348 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000234C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002350 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002354 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002358 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000235C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002360 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002364 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002368 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000236C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002370 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002374 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002378 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000237C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0002480 | other | 0/0 | 0/0 | 0/3 |  | - |
| B0002484 | other | 0/0 | 0/0 | 1/2 |  | - |
| B0002488 | other | 0/0 | 0/0 | 0/2 |  | - |
| B0002490 | other | 0/0 | 0/0 | 5/6 |  | CSR storage |
| B0002494 | other | 0/0 | 0/0 | 5/7 |  | CSR storage |
| B0002498 | other | 0/0 | 0/0 | 4/5 |  | CSR storage |
| B00024A8 | other | 0/0 | 0/0 | 0/2 |  | - |
| B0004000 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004004 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004008 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000400C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004010 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004014 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004028 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000402C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004030 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004034 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004038 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000403C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004040 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004044 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004048 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000404C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004100 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004104 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004108 | other | 0/1 | 0/1 | 0/2 |  | - |
| B000410C | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004110 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004114 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004118 | other | 0/1 | 0/1 | 0/2 |  | - |
| B000411C | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004120 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004124 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004128 | other | 0/1 | 0/1 | 0/2 |  | - |
| B000412C | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004130 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004134 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004138 | other | 0/1 | 0/1 | 0/2 |  | - |
| B000413C | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004140 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004144 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004148 | other | 0/1 | 0/1 | 0/2 |  | - |
| B000414C | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004150 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004154 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004158 | other | 0/1 | 0/1 | 0/2 |  | - |
| B000415C | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004160 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004164 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004168 | other | 0/1 | 0/1 | 0/2 |  | - |
| B000416C | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004170 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004174 | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004178 | other | 0/1 | 0/1 | 0/2 |  | - |
| B000417C | other | 0/1 | 0/1 | 0/2 |  | - |
| B0004200 | other | 0/0 | 0/0 | 6/6 |  | modelled |
| B0004300 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004304 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004308 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000430C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004310 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004314 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004318 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000431C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0004320 | other | 0/0 | 0/0 | 0/5 |  | - |
| B0004324 | other | 0/0 | 0/0 | 0/5 |  | - |
| B0004500 | other | 0/0 | 0/0 | 3/3 |  | CSR storage |
| B0004504 | other | 0/0 | 0/0 | 4/4 |  | CSR storage |
| B0006000 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006004 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006008 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000600C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006010 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006014 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006018 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000601C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006020 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006024 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006028 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000602C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006030 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006034 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0006038 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000603C | other | 0/0 | 0/0 | 2/2 |  | CSR storage |
| B0006040 | other | 0/0 | 0/0 | 12/0 |  | CSR storage |
| B0008000 | other | 0/0 | 0/0 | 2/3 |  | CSR storage |
| B0008004 | other | 0/0 | 0/0 | 0/1 |  | - |
| B0008008 | other | 0/0 | 0/0 | 0/1 |  | - |
| B000800C | other | 0/0 | 0/0 | 0/1 |  | - |
| B0008010 | other | 0/0 | 0/0 | 2/2 |  | CSR storage |
| B0008018 | other | 0/0 | 0/0 | 1/1 |  | CSR storage |
| B0008020 | other | 0/0 | 0/0 | 4/4 |  | CSR storage |
| B0008024 | other | 0/0 | 0/0 | 4/4 |  | CSR storage |
| B0008028 | other | 0/0 | 0/0 | 3/3 |  | CSR storage |
| B0008084 | other | 0/0 | 0/0 | 4/4 |  | CSR storage |
| B0009000 | GPU/blitter | 0/1 | 0/1 | 0/1 |  | - |
| B0009010 | GPU/blitter | 0/5 | 0/5 | 32/33 | 0x0 | modelled |
| B0009030 | GPU/blitter | 0/1 | 0/1 | 0/1 |  | - |
| B0009090 | GPU/blitter | 0/2 | 0/2 | 0/0 |  | - |
| B00090C0 | GPU/blitter | 0/0 | 0/0 | 0/8 |  | - |
| B0009100 | GPU/blitter | 0/0 | 0/0 | 0/8 |  | modelled |
| B0009120 | GPU/blitter | 1/0 | 1/0 | 0/0 | 0x20 | modelled |
| B0009122 | GPU/blitter | 0/0 | 0/0 | 8/0 | 0x1000 | modelled |
| B0009130 | GPU/blitter | 0/2 | 0/2 | 0/8 |  | modelled |
| B0009142 | GPU/blitter | 0/0 | 0/0 | 8/0 | 0x0 | modelled |
| B0009150 | GPU/blitter | 0/2 | 0/2 | 0/8 |  | - |
| B0009180 | GPU/blitter | 0/2 | 0/2 | 0/8 |  | - |
| B0009220 | other | 0/0 | 0/0 | 0/16 |  | - |
| B000A000 | demux (pace_section_demux) | 0/6 | 0/6 | 6/8 | 0xf00 | CSR storage |
| B000A004 | demux (pace_section_demux) | 4/2 | 4/2 | 2/4 | 0x3f10 | - |
| B000A00C | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A010 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A014 | demux (pace_section_demux) | 0/1 | 0/1 | 0/1 |  | - |
| B000A018 | demux (pace_section_demux) | 0/1 | 0/1 | 0/1 |  | - |
| B000A01C | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A020 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A024 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A028 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A02C | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A030 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A034 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A038 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A03C | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A040 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A044 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A048 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A04C | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A050 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A054 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A058 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A05C | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A060 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A064 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A068 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A06C | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A070 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A074 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A078 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A07C | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A080 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A084 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A088 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A08C | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A090 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A094 | demux (pace_section_demux) | 0/0 | 0/0 | 2/3 | 0x0 | - |
| B000A098 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A0A8 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A0B0 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A0B4 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A0B8 | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A0BC | demux (pace_section_demux) | 0/0 | 0/0 | 0/2 |  | - |
| B000A0C0 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A0D0 | demux (pace_section_demux) | 0/0 | 0/0 | 0/1 |  | - |
| B000A0D8 | demux (pace_section_demux) | 0/0 | 0/0 | 10/11 | 0xff800000 | CSR storage |
| B000A0DC | demux (pace_section_demux) | 0/0 | 0/0 | 10/11 | 0xff800000 | CSR storage |
| B000A0E0 | demux (pace_section_demux) | 0/0 | 0/0 | 6/6 | 0xc0004000 | CSR storage |
| B000A120 | demux (pace_section_demux) | 0/1 | 0/1 | 0/1 |  | - |
| B000A124 | demux (pace_section_demux) | 10/10 | 10/10 | 168/168 | 0x8058 | CSR storage |
| B000A128 | demux (pace_section_demux) | 2/8 | 2/8 | 0/168 | 0x20b4 | - |
| B000A140 | demux (pace_section_demux) | 0/1 | 0/1 | 31/33 | 0x100001 | CSR storage |
| B000A144 | demux (pace_section_demux) | 42/42 | 42/42 | 442/442 | 0x806c | CSR storage |
| B000A148 | demux (pace_section_demux) | 24/18 | 24/18 | 0/442 | 0x0 | - |
| B000B004 | other | 0/0 | 0/0 | 3/0 |  | CSR storage |
| B000B804 | other | 0/0 | 0/0 | 6/0 |  | CSR storage |
| B000B814 | other | 0/0 | 0/0 | 2/3 |  | modelled |
| B000B864 | other | 0/0 | 0/0 | 0/13 |  | - |
| B000B868 | other | 0/0 | 0/0 | 0/6 |  | - |
| B000B86C | other | 0/0 | 0/0 | 0/1 |  | - |
| B000BFFC | other | 0/0 | 0/0 | 1/2 |  | CSR storage |
| B000D010 | EMMA timer | 0/1 | 0/1 | 0/2 |  | - |
| B000D020 | EMMA timer | 1/1 | 1/1 | 1/1 | 0x1 | modelled |
| B000D030 | EMMA timer | 2/2 | 2/2 | 2/2 | 0x1 | modelled |
| B000D050 | EMMA timer | 0/1 | 0/1 | 0/1 | 0xc5c10 | modelled |
| B000D0C0 | EMMA timer | 1/1 | 1/1 | 1/1 | 0x1 | modelled |
| B000D0D0 | EMMA timer | 3656/0 | 88/0 | 9865/0 | 0x0 | CSR storage |
| B000D0E0 | EMMA timer | 0/3656 | 0/88 | 0/9865 |  | modelled |
| B2000140 | other | 1/1 | 1/1 | 1/1 |  | CSR storage |
| B2001000 | other | 0/266 | 0/1 | 0/2 |  | modelled |
| B2001010 | other | 0/1 | 0/1 | 0/214 |  | - |
| B2001013 | other | 0/0 | 0/0 | 106/0 | 0xf | - |
| B2001020 | other | 0/1 | 0/1 | 1/2 | 0x1 | CSR storage |
| B2001030 | other | 0/2 | 0/2 | 0/7 |  | - |
| B2001033 | other | 0/0 | 0/0 | 3/0 | 0x80 | - |
| B2001040 | other | 0/0 | 0/0 | 0/3 |  | - |
| B2001043 | other | 0/0 | 0/0 | 2/0 | 0x3 | - |
| B2001050 | other | 773524/0 | 553/0 | 0/0 | 0x60 | modelled |
| B2001060 | other | 0/0 | 0/0 | 2/0 | 0x0 | CSR storage |
| B2002000 | serial0 (front panel link) | 0/0 | 0/0 | 2/3 | 0xc8 | CSR storage |
| B2002030 | serial0 (front panel link) | 0/0 | 0/0 | 0/1 |  | CSR storage |
| B2002040 | serial0 (front panel link) | 0/0 | 0/0 | 0/1 |  | CSR storage |
| B2002050 | serial0 (front panel link) | 0/0 | 0/0 | 0/6 |  | CSR storage |
| B2002060 | serial0 (front panel link) | 0/0 | 0/0 | 6/6 | 0x2 | modelled |
| B2002070 | serial0 (front panel link) | 0/0 | 0/0 | 3/4 | 0x4 | modelled |
| B2006000 | I2C | 0/4 | 0/4 | 0/28138 |  | CSR storage |
| B2006010 | I2C | 2/0 | 1/0 | 37210/0 | 0x4 | modelled |
| B2006020 | I2C | 2/2 | 2/2 | 2/2 | 0x0 | CSR storage |
| B2006040 | I2C | 0/2 | 0/1 | 20201/13299 | 0x0 | modelled |
| B2006050 | I2C | 0/4 | 0/2 | 0/37210 |  | modelled |
| B2006060 | I2C | 0/4 | 0/2 | 0/7420 |  | modelled |
| B2009000 | serial/clock | 0/1 | 0/1 | 0/1 |  | modelled |
| B2009010 | serial/clock | 397/398 | 54/55 | 1507/1508 | 0x0 | modelled |
| B2009020 | serial/clock | 794/398 | 108/55 | 3014/1508 | 0x1 | modelled |
| B2009030 | serial/clock | 1/1 | 1/1 | 1/1 | 0x0 | modelled |
| B200A000 | serial/clock | 772/768 | 111/107 | 2880/2877 | 0x0 | modelled |
| B200A020 | serial/clock | 0/0 | 0/0 | 51/0 |  | CSR storage |
| B200A040 | serial/clock | 4/4 | 4/4 | 55/4 | 0x1 | CSR storage |
| B200A050 | serial/clock | 1/1 | 1/1 | 1/1 |  | CSR storage |
| B200A060 | serial/clock | 4/4 | 4/4 | 4/4 | 0x81 | CSR storage |
| B200A070 | serial/clock | 1/1 | 1/1 | 1/1 |  | CSR storage |
| B200A080 | serial/clock | 0/1 | 0/1 | 8/9 | 0x80 | CSR storage |
| B200A090 | serial/clock | 0/1 | 0/1 | 0/1 |  | CSR storage |
| B200A0A0 | serial/clock | 0/1 | 0/1 | 2/3 | 0x0 | CSR storage |
| B200A0B0 | serial/clock | 0/1 | 0/1 | 0/1 |  | CSR storage |
| B4080000 | external 16550 UART | 0/0 | 0/0 | 3/4 | 0x80 | modelled |
| B4080001 | external 16550 UART | 0/0 | 0/0 | 0/5 |  | - |
| B4080002 | external 16550 UART | 0/0 | 0/0 | 7/15 | 0xf | - |
| B4080003 | external 16550 UART | 0/0 | 0/0 | 0/1 |  | - |
| B4080005 | external 16550 UART | 0/0 | 0/0 | 2/0 | 0x0 | - |
| B4080007 | external 16550 UART | 0/0 | 0/0 | 2/3 | 0x3 | - |
| B4080100 | other | 0/0 | 0/0 | 0/2 |  | - |
| B4080101 | other | 0/0 | 0/0 | 0/2 |  | - |
| B4080102 | other | 0/0 | 0/0 | 0/2 |  | - |
| B4080103 | other | 0/0 | 0/0 | 0/2 |  | - |
| B4080106 | other | 0/0 | 0/0 | 2/2 |  | - |
| B4180000 | other | 0/9 | 0/7 | 0/5359 |  | - |
