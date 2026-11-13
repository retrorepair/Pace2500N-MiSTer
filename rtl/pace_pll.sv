// One 1350 MHz VCO (50 MHz x 27):
//  outclk_0  50.0  MHz  core / CPU / DDR port 1     (VCO / 27)
//  outclk_1  54.0  MHz  video (4 x BT.601 13.5 MHz) (VCO / 25)
//  outclk_2  90.0  MHz  MPEG decoder memory, DDR port 2 (VCO / 15)
//  outclk_3  79.41 MHz  MPEG decoder compute        (VCO / 17)
//  outclk_4  27.0  MHz  MPEG decoder dot clock      (VCO / 50), phase-aligned to outclk_1
//  outclk_5  75.0  MHz  CPU core (pace_r4k clk2x)    (VCO / 18)
//  outclk_6  37.5  MHz  CPU memory side (clk1x)      (VCO / 36), phase-aligned to outclk_5
module pll(input wire refclk, rst, output wire outclk_0, outclk_1, outclk_2, outclk_3, outclk_4, outclk_5, outclk_6, locked);
    pace_pll_impl pll_inst(.refclk(refclk), .rst(rst), .outclk_0(outclk_0), .outclk_1(outclk_1),
        .outclk_2(outclk_2), .outclk_3(outclk_3), .outclk_4(outclk_4), .outclk_5(outclk_5), .outclk_6(outclk_6), .locked(locked));
endmodule
`timescale 1ns/10ps
module  pace_pll_impl(

	// interface 'refclk'
	input wire refclk,

	// interface 'reset'
	input wire rst,

	// interface 'outclk0'
	output wire outclk_0,
	output wire outclk_1,
	output wire outclk_2,
	output wire outclk_3,
	output wire outclk_4,
	output wire outclk_5,
	output wire outclk_6,

	// interface 'locked'
	output wire locked
);

	altera_pll #(
		.fractional_vco_multiplier("true"),
		.reference_clock_frequency("50.0 MHz"),
		.operation_mode("direct"),
		.number_of_clocks(7),
		.output_clock_frequency0("50.000000 MHz"),
		.phase_shift0("0 ps"),
		.duty_cycle0(50),
		.output_clock_frequency1("54.000000 MHz"),
		.phase_shift1("0 ps"),
		.duty_cycle1(50),
		.output_clock_frequency2("90.000000 MHz"),
		.phase_shift2("0 ps"),
		.duty_cycle2(50),
		.output_clock_frequency3("79.411764 MHz"),
		.phase_shift3("0 ps"),
		.duty_cycle3(50),
		.output_clock_frequency4("27.000000 MHz"),
		.phase_shift4("0 ps"),
		.duty_cycle4(50),
		.output_clock_frequency5("75.000000 MHz"),
		.phase_shift5("0 ps"),
		.duty_cycle5(50),
		.output_clock_frequency6("37.500000 MHz"),
		.phase_shift6("0 ps"),
		.duty_cycle6(50),
		.output_clock_frequency7("0 MHz"),
		.phase_shift7("0 ps"),
		.duty_cycle7(50),
		.output_clock_frequency8("0 MHz"),
		.phase_shift8("0 ps"),
		.duty_cycle8(50),
		.output_clock_frequency9("0 MHz"),
		.phase_shift9("0 ps"),
		.duty_cycle9(50),
		.output_clock_frequency10("0 MHz"),
		.phase_shift10("0 ps"),
		.duty_cycle10(50),
		.output_clock_frequency11("0 MHz"),
		.phase_shift11("0 ps"),
		.duty_cycle11(50),
		.output_clock_frequency12("0 MHz"),
		.phase_shift12("0 ps"),
		.duty_cycle12(50),
		.output_clock_frequency13("0 MHz"),
		.phase_shift13("0 ps"),
		.duty_cycle13(50),
		.output_clock_frequency14("0 MHz"),
		.phase_shift14("0 ps"),
		.duty_cycle14(50),
		.output_clock_frequency15("0 MHz"),
		.phase_shift15("0 ps"),
		.duty_cycle15(50),
		.output_clock_frequency16("0 MHz"),
		.phase_shift16("0 ps"),
		.duty_cycle16(50),
		.output_clock_frequency17("0 MHz"),
		.phase_shift17("0 ps"),
		.duty_cycle17(50),
		.pll_type("General"),
		.pll_subtype("General")
	) altera_pll_i (
		.rst	(rst),
		.outclk	({outclk_6,outclk_5,outclk_4,outclk_3,outclk_2,outclk_1,outclk_0}),
		.locked	(locked),
		.fboutclk	( ),
		.fbclk	(1'b0),
		.refclk	(refclk)
	);
endmodule

