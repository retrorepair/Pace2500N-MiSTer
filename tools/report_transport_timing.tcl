project_open Pace2500N
create_timing_netlist
read_sdc
update_timing_netlist
report_timing -setup -npaths 10 -nworst 1 -detail full_path -file output_files/transport_critical_paths.rpt
delete_timing_netlist
project_close
