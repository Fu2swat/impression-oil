@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

if exist "%CD%\.venv\Scripts\python.exe" (
  "%CD%\.venv\Scripts\python.exe" -m impression_oil %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 -m impression_oil %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python -m impression_oil %*
  exit /b %ERRORLEVEL%
)

echo Python 3 was not found. Install Python 3.10 or later, then run this file again.
exit /b 1
