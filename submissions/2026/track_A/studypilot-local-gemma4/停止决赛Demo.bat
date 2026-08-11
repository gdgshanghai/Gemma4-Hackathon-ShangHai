@echo off
setlocal
set "CORE=%~dp0"
if exist "%~dp0..\..\scripts\final_competition_launcher.ps1" set "CORE=%~dp0..\.."
for /d %%D in ("%~dp002_*") do if exist "%%~fD\scripts\final_competition_launcher.ps1" set "CORE=%%~fD"
if not exist "%CORE%\scripts\final_competition_launcher.ps1" (
  echo Finals launcher not found.
  if not defined STUDYPILOT_NO_PAUSE pause
  exit /b 1
)
set "CHECK_ONLY="
if /i "%~1"=="--check" set "CHECK_ONLY=-CheckOnly"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%CORE%\scripts\final_competition_launcher.ps1" -Action Stop %CHECK_ONLY%
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Finals Demo stop failed. Review the message above.
  if not defined STUDYPILOT_NO_PAUSE pause
)
exit /b %EXIT_CODE%
