@echo off
setlocal
set "PPT="
for /d %%D in ("%~dp001_*") do for %%F in ("%%~fD\*V11*.pptx") do if exist "%%~fF" set "PPT=%%~fF"
for %%F in ("%~dp0materials\*V11*.pptx") do if exist "%%~fF" set "PPT=%%~fF"
for %%F in ("%~dp0..\assets\*V11*.pptx") do if exist "%%~fF" set "PPT=%%~fF"
if not defined PPT (
  echo V11 finals PPT not found.
  if not defined STUDYPILOT_NO_PAUSE pause
  exit /b 1
)
if /i "%~1"=="--check" (
  echo Finals wrapper check: PASS ^(PPT^)
  exit /b 0
)
start "" "%PPT%"
exit /b 0
