@echo off
setlocal DisableDelayedExpansion
set "PACE_INSTALL_PATH=%LOCALAPPDATA%\Pace2500N\Portable"
echo Pace Channel Builder portable setup
echo Close any running copy before installing.
echo.
echo Default folder: "%PACE_INSTALL_PATH%"
set /p "PACE_INSTALL_PATH=Press Enter to use it, or type a full folder path: "
if not exist "%~dp0PC\PaceChannelBuilder\PaceChannelBuilder.exe" goto missing
robocopy "%~dp0PC\PaceChannelBuilder" "%PACE_INSTALL_PATH%" /E /XJ /R:1 /W:1 /XD data /NFL /NDL /NJH /NJS /NP
if errorlevel 8 goto failed
robocopy "%~dp0PC\PaceChannelBuilder\data" "%PACE_INSTALL_PATH%\data" /E /XJ /R:1 /W:1 /XC /XN /XO /NFL /NDL /NJH /NJS /NP
if errorlevel 8 goto failed
echo Installed in "%PACE_INSTALL_PATH%".
powershell.exe -NoProfile -Command "$desktop=[Environment]::GetFolderPath('Desktop'); if($desktop){$shell=New-Object -ComObject WScript.Shell; $link=$shell.CreateShortcut((Join-Path $desktop 'Pace Channel Builder (Portable).lnk')); $link.TargetPath=(Join-Path $env:PACE_INSTALL_PATH 'PaceChannelBuilder.exe'); $link.WorkingDirectory=$env:PACE_INSTALL_PATH; $link.Save()}"
start "" /D "%PACE_INSTALL_PATH%" "%PACE_INSTALL_PATH%\PaceChannelBuilder.exe"
exit /b 0

:missing
echo Extract the whole ZIP before running this installer.
pause
exit /b 1

:failed
echo Setup could not copy every file. Close Channel Builder and choose a folder you can write to.
pause
exit /b 1
