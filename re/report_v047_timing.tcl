project_open Pace2500N
create_timing_netlist
read_sdc
update_timing_netlist
report_timing -setup -npaths 3 -detail full_path -file ../../re/v047_timing_paths.txt
project_close
