# Core CPU and DDR interface run on the PLL-derived 50 MHz clock (general[0]).
# Root and derived PLL clocks are constrained by sys/sys_top.sdc.
# v0.5.0: video raster/scanout run on the 54 MHz PLL output (general[1]).
# pace_guide_video601 crosses between them only through toggle handshakes
# and dual-clock RAMs, so the two PLL outputs are timed as asynchronous.
# v0.5.8: MPEG decoder clocks. The decoder crosses between its compute (general[3]),
# memory (general[2]) and dot (general[4]) clocks through its own dual-clock FIFOs
# and synchronisers (rtl/mpeg2), and reaches the core only through vidfeed_cdc and
# 2-FF level synchronisers. general[4] (27 MHz) and general[1] (54 MHz) share the
# VCO with aligned edges: the decoder's pixels are sampled directly in the video
# clock, so that pair stays timed.
# v0.7: the CPU (pace_r4k): core general[5] (75 MHz) and memory side general[6] (37.5 MHz), one
# VCO, edges aligned, crossing without synchronisers inside the CPU, so the pair is timed
# together. It reaches clk_sys only through pace_r4k's toggle handshakes (payloads held still
# while the toggle crosses) and the 2-FF reset/interrupt synchronisers.
set_clock_groups -asynchronous \
   -group [get_clocks {emu|pll|pll_inst|altera_pll_i|general[0].gpll~PLL_OUTPUT_COUNTER|divclk}] \
   -group [get_clocks {emu|pll|pll_inst|altera_pll_i|general[1].gpll~PLL_OUTPUT_COUNTER|divclk emu|pll|pll_inst|altera_pll_i|general[4].gpll~PLL_OUTPUT_COUNTER|divclk}] \
   -group [get_clocks {emu|pll|pll_inst|altera_pll_i|general[2].gpll~PLL_OUTPUT_COUNTER|divclk}] \
   -group [get_clocks {emu|pll|pll_inst|altera_pll_i|general[3].gpll~PLL_OUTPUT_COUNTER|divclk}]    -group [get_clocks {emu|pll|pll_inst|altera_pll_i|general[5].gpll~PLL_OUTPUT_COUNTER|divclk emu|pll|pll_inst|altera_pll_i|general[6].gpll~PLL_OUTPUT_COUNTER|divclk}]
