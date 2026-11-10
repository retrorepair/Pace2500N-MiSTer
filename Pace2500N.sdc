# Core CPU and DDR interface run on the PLL-derived 50 MHz clock (general[0]).
# Root and derived PLL clocks are constrained by sys/sys_top.sdc.
# v0.5.0: video raster/scanout run on the 54 MHz PLL output (general[1]).
# pace_guide_video601 crosses between them only through toggle handshakes
# and dual-clock RAMs, so the two PLL outputs are timed as asynchronous.
set_clock_groups -asynchronous \
   -group [get_clocks {emu|pll|pll_inst|altera_pll_i|general[0].gpll~PLL_OUTPUT_COUNTER|divclk}] \
   -group [get_clocks {emu|pll|pll_inst|altera_pll_i|general[1].gpll~PLL_OUTPUT_COUNTER|divclk}]
