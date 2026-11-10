onerror {quit -code 1}
if {![file isdirectory sim/work]} {vlib sim/work}
vlog -work sim/work -sv sim/tb_boot.sv rtl/pace_firmware_cpu.sv rtl/pace_bootrom.sv
vsim -onfinish stop -work sim/work tb_boot
run -all
quit -code 0
