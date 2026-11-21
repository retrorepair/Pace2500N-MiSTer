$ErrorActionPreference='Stop'
$projectRoot='C:\Users\joelw\Downloads\Pace2500N_RealFirmwareBoot_v042_with_handoff\Pace2500N'
$buildRoot=Join-Path $env:TEMP 'Pace2500N_cold_ttx100_20261121'
$evidenceRoot=Join-Path $projectRoot 're/deployment/coldboot_20261121'
if(Get-Process -Name quartus_fit,quartus_sh -ErrorAction SilentlyContinue){throw 'Another Quartus build is running'}
Push-Location -LiteralPath $buildRoot
try {
 & C:/intelFPGA_lite/17.0/quartus/bin64/quartus_sh.exe --flow compile Pace2500N *> compile.log
 $compileExit=$LASTEXITCODE
} finally {Pop-Location}
if($compileExit){throw "V080A compilation failed: $compileExit"}
if([IO.File]::ReadAllText((Join-Path $buildRoot 'compile.log')) -notmatch 'Full Compilation was successful'){throw 'Full compilation did not succeed'}
$timing=[IO.File]::ReadAllText((Join-Path $buildRoot 'output_files/Pace2500N.sta.summary'))
$checks=@([regex]::Matches($timing,'Type\s*:\s*([^\r\n]+)\r?\nSlack\s*:\s*([-0-9.]+)') | ForEach-Object {
 [pscustomobject]@{Type=$_.Groups[1].Value;Slack=[double]$_.Groups[2].Value}
})
$coreChecks=@($checks | Where-Object Type -NotMatch 'pll_hdmi')
if($coreChecks.Count -ne 48){throw "Expected 48 non-HDMI checks, found $($coreChecks.Count)"}
$coreChecks | ConvertTo-Json | Set-Content (Join-Path $evidenceRoot 'V080A-timing.json')
$failures=@($coreChecks | Where-Object Slack -LT 0)
if($failures.Count){$failures | Format-Table;Write-Output 'EXPERIMENTAL timing misses; user authorised hardware testing of marginal builds'}
Set-Location -LiteralPath $projectRoot
$rbf=Join-Path $projectRoot 'output_files/Pace2500N_V080A.rbf'
& C:/intelFPGA_lite/17.0/quartus/bin64/quartus_cpf.exe -c -o bitstream_compression=on (Join-Path $buildRoot 'output_files/Pace2500N.sof') $rbf
if($LASTEXITCODE){throw 'RBF conversion failed'}
& scp -q -O -o BatchMode=yes -o HostKeyAlias=MiSTer $rbf Pace2500N_V080A_Live.mgl root@192.168.1.103:/media/fat/_Other/
if($LASTEXITCODE){throw 'RBF/MGL upload failed'}
$expectedHash=(Get-FileHash -LiteralPath $rbf -Algorithm SHA256).Hash.ToLowerInvariant()
$remoteHash=& ssh -o BatchMode=yes -o HostKeyAlias=MiSTer root@192.168.1.103 'sha256sum /media/fat/_Other/Pace2500N_V080A.rbf'
if($LASTEXITCODE -or $remoteHash -notmatch "^$expectedHash "){throw 'Uploaded RBF hash mismatch'}
$testLog=Join-Path $evidenceRoot 'V080A-test.log'
& ssh -o BatchMode=yes -o HostKeyAlias=MiSTer root@192.168.1.103 'sh /media/fat/linux/pace/ttx-hardware-test.sh' | Tee-Object -FilePath $testLog
if($LASTEXITCODE){throw 'Hardware test failed; restore trap returns to V079Z'}
$remoteEvidence=@(Get-Content $testLog | Where-Object {$_ -match '^/media/fat/linux/pace/re-evidence/coldboot_20261121/V080A-[0-9]{6}$'})
if($remoteEvidence.Count -ne 1){throw 'Unexpected evidence folder response'}
$localEvidence=Join-Path $evidenceRoot ($remoteEvidence[0] -split '/')[-1]
New-Item -ItemType Directory -Path $localEvidence -Force | Out-Null
& scp -q -O -r -o BatchMode=yes -o HostKeyAlias=MiSTer ('root@192.168.1.103:'+$remoteEvidence[0]) $evidenceRoot
if($LASTEXITCODE){throw 'Evidence download failed'}
Write-Output "V080A complete; evidence: $localEvidence"
