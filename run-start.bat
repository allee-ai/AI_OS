@echo off
REM Change to the directory where this batch file lives
cd /d "%~dp0"

REM Prefer a native Windows start script if present
if exist start.bat (
  call start.bat
  goto :eof
)

REM Try WSL first, then bash (Git Bash/msys)
where wsl >nul 2>&1
if %ERRORLEVEL%==0 (
  wsl bash ./start.sh
  goto :eof
)

where bash >nul 2>&1
if %ERRORLEVEL%==0 (
  bash ./start.sh
  goto :eof
)

echo No suitable shell found to run start.sh. Run it manually.
pause
