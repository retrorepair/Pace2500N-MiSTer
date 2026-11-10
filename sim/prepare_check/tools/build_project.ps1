# Standard Windows PowerShell 5+: prepares an ordinary MiSTer sys_top Quartus
# project without Python or third-party downloader requirements.
param([switch]$Compile)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$reference = Join-Path $root 'reference\Arcade-KillerInstinct_MiSTer'
$sourceQsf = Join-Path $reference 'KillerInstinct.qsf'
$bundledQsf = Join-Path $PSScriptRoot 'mister_platform.qsf'
if ((Test-Path $bundledQsf) -and (Test-Path (Join-Path $root 'sys\sys_top.v'))) {
    $sourceQsf = $bundledQsf
}
if (-not (Test-Path $sourceQsf)) {
    $refDir = Join-Path $root 'reference'
    New-Item -Force -ItemType Directory -Path $refDir | Out-Null
    $zip = Join-Path $refDir 'ki_main.zip'
    $extractDir = Join-Path $refDir 'temp_extract'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Write-Host 'Downloading public MiSTer Killer Instinct platform repository...'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/MiSTer-devel/Arcade-KillerInstinct_MiSTer/archive/refs/heads/main.zip' -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $extractDir -Force
    $upstream = Get-ChildItem -Path $extractDir -Directory | Where-Object { $_.Name -like 'Arcade-KillerInstinct_MiSTer-*' } | Select-Object -First 1
    if (-not $upstream) { throw 'Could not locate Killer Instinct sources in the download' }
    Move-Item -Path $upstream.FullName -Destination $reference
    Remove-Item $extractDir -Recurse -Force
    Remove-Item $zip -Force
}
$sourceSys = Join-Path $reference 'sys'
if (-not (Test-Path (Join-Path $root 'sys\sys_top.v'))) {
    if (-not (Test-Path (Join-Path $sourceSys 'sys_top.v'))) { throw 'Missing MiSTer sys_top.v in reference' }
    Copy-Item -Path $sourceSys -Destination (Join-Path $root 'sys') -Recurse -Force
}
$qsf = [IO.File]::ReadAllText($sourceQsf)
if (-not $qsf.Contains('source files.qip')) { throw 'Upstream QSF format changed; cannot find files.qip source' }
$qsf = $qsf.Replace('source files.qip', "source files.qip`r`nset_global_assignment -name SDC_FILE Pace2500N.sdc")
[IO.File]::WriteAllText((Join-Path $root 'Pace2500N.qsf'), $qsf)
[IO.File]::WriteAllText((Join-Path $root 'Pace2500N.qpf'), 'PROJECT_REVISION = "Pace2500N"' + [Environment]::NewLine)
Write-Host 'Ready: Pace2500N.qpf. MiSTer sys_top, pinout, and HPS shell imported.'
Write-Host 'Building actual U202 bootloader CPU + MiSTer DDR3 + PAL 576i monitor.'
Write-Host 'Quartus Prime Standard required to generate output_files/Pace2500N.rbf.'
if ($Compile -and (Get-Command quartus_sh -ErrorAction SilentlyContinue)) {
    & quartus_sh --flow compile Pace2500N
    if ($LASTEXITCODE -ne 0) { throw "Quartus compilation failed: $LASTEXITCODE" }
} else {
    Write-Host 'Preparation only. Run Analysis & Synthesis first; use -Compile explicitly for a full build.'
}
