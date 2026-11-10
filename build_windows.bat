@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "tools\build_project.ps1"
if errorlevel 1 (echo Build failed. Read the error above.& pause & exit /b 1)
echo.
echo Copy output_files\Pace2500N.rbf to MiSTer _Other after a successful compile.
pause
