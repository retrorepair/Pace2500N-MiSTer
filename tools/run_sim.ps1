param(
    [ValidateSet('boot','strict','memory','m16_pc','debug_uart','pal576i','oracle','fetch','timer','muldiv','all')][string]$Test='all',
    [string]$ModelSim='C:\intelFPGA_lite\17.0\modelsim_ase\win32aloem'
)
$ErrorActionPreference='Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    if(-not (Test-Path sim/work)) {
        & "$ModelSim/vlib.exe" sim/work
        if($LASTEXITCODE -ne 0) { throw 'vlib failed' }
    }
    $tests=if($Test -eq 'all') { @('boot','strict','memory','m16_pc','debug_uart','pal576i','oracle','fetch','timer','muldiv') } else { @($Test) }
    foreach($item in $tests) {
        [string[]]$sources=if($item -eq 'debug_uart') { @('rtl/pace_debug_uart.sv') }
                 elseif($item -eq 'pal576i') { @('rtl/pace_pal576i.sv') }
                 else { @('rtl/pace_firmware_cpu.sv','rtl/pace_bootrom.sv','rtl/pace_muldiv.sv') }
        & "$ModelSim/vlog.exe" -work sim/work -sv +incdir+sim "sim/tb_$item.sv" @sources
        if($LASTEXITCODE -ne 0) { throw "Compilation failed: $item" }
        $log="sim/$item.log"
        & "$ModelSim/vsim.exe" -c -work sim/work "tb_$item" -l $log -do 'onbreak {quit -code 1}; run -all; quit -code 0'
        if($LASTEXITCODE -ne 0) { throw "Simulation failed: $item" }
        $transcript=Get-Content -Raw $log
        if($transcript -notmatch '# PASS:' -or $transcript -match '\*\* (Fatal|Error):') {
            throw "No clean PASS in $log"
        }
    }
} finally { Pop-Location }
