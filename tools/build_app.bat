@echo off
rem Builds the standalone Windows app: dist\PaceChannelBuilder\PaceChannelBuilder.exe
rem The result needs nothing installed: Python, ffmpeg and yt-dlp are inside the folder.
rem Build machine only: Python 3 + PyInstaller (py -3 -m pip install pyinstaller) and the
rem gyan.dev ffmpeg "release essentials" build unzipped in third_party\.
cd /d "%~dp0\.."
rem Rebuilding deletes dist\PaceChannelBuilder first; with the app open that half-deletes
rem the folder it runs from (including ffmpeg), so playout breaks at the next programme.
tasklist /fi "imagename eq PaceChannelBuilder.exe" | find /i "PaceChannelBuilder.exe" >nul && (
  echo Close Pace Channel Builder first - the build replaces the files it is running from.
  exit /b 1
)
py -3 -m PyInstaller --noconfirm --windowed --name PaceChannelBuilder --paths tools ^
  --hidden-import pace_huffman --hidden-import pace_si --hidden-import pace_transport ^
  --workpath "%TEMP%\pace_app_build" --distpath dist --specpath "%TEMP%\pace_app_build" tools\pace_builder.pyw || exit /b 1
mkdir dist\PaceChannelBuilder\tools 2>nul
for /d %%D in (third_party\ffmpeg-*) do (
  copy /y "%%D\bin\ffmpeg.exe" dist\PaceChannelBuilder\tools\ >nul
  copy /y "%%D\bin\ffprobe.exe" dist\PaceChannelBuilder\tools\ >nul
  copy /y "%%D\bin\ffplay.exe" dist\PaceChannelBuilder\tools\ >nul
  copy /y "%%D\LICENSE" dist\PaceChannelBuilder\tools\FFMPEG_LICENSE.txt >nul
  copy /y "%%D\README.txt" dist\PaceChannelBuilder\tools\FFMPEG_README.txt >nul
)
if not exist third_party\yt-dlp.exe curl -sSL -o third_party\yt-dlp.exe https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
copy /y third_party\yt-dlp.exe dist\PaceChannelBuilder\tools\ >nul
echo Built dist\PaceChannelBuilder\PaceChannelBuilder.exe
