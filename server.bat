@echo off
setlocal enabledelayedexpansion

rem server.bat: A script to manage the Gerrit MCP server.

set "SCRIPT_DIR=%~dp0"
set "SERVER_COMMAND=%SCRIPT_DIR%.venv\Scripts\uvicorn.exe gerrit_mcp_server.main:app --host 127.0.0.1 --port 6322"
set "PID_FILE=%SCRIPT_DIR%server.pid"
set "LOG_FILE=%SCRIPT_DIR%server.log"

if "%~1"=="start" goto :start
if "%~1"=="stop" goto :stop
if "%~1"=="restart" goto :restart
if "%~1"=="status" goto :status
if "%~1"=="logs" goto :logs

echo Usage: %~nx0 ^{start^|stop^|restart^|status^|logs^}
exit /b 1

:is_running
if exist "%PID_FILE%" (
  set /p PID=<"%PID_FILE%"
  tasklist /fi "PID eq !PID!" | findstr /r /c:"^[ ]*[A-Za-z]" >nul
  if not errorlevel 1 exit /b 0
)
exit /b 1

:start
call :is_running
if not errorlevel 1 (
  echo Server is already running with PID !PID!.
  exit /b 1
)

echo Starting server...
if not exist "%SCRIPT_DIR%.venv\Scripts\uvicorn.exe" (
  echo Error: uvicorn not found. Run build-gerrit.bat first.
  exit /b 1
)

start "Gerrit MCP Server" /b cmd /c "%SERVER_COMMAND% >> \"%LOG_FILE%\" 2>&1"
for /f "tokens=2 delims==" %%P in ('wmic process where "CommandLine like '%%uvicorn.exe%%gerrit_mcp_server.main:app%%'" get ProcessId /value ^| find "ProcessId"') do (
  set "PID=%%P"
  goto :gotpid
)

echo Error: Server failed to start. Check "%LOG_FILE%" for details.
exit /b 1

:gotpid
echo !PID!>"%PID_FILE%"
echo Server started successfully with PID !PID!.
echo Logs are being written to %LOG_FILE%.
exit /b 0

:stop
call :is_running
if errorlevel 1 (
  echo Server is not running.
  if exist "%PID_FILE%" (
    echo Cleaning up stale PID file: %PID_FILE%
    del "%PID_FILE%"
  )
  exit /b 0
)

echo Stopping server with PID !PID!...
taskkill /pid !PID! /t >nul
if errorlevel 1 (
  echo Error: Failed to stop PID !PID!.
  exit /b 1
)
del "%PID_FILE%"
echo Server stopped successfully.
exit /b 0

:restart
echo Restarting server...
call "%~f0" stop
call "%~f0" start
exit /b 0

:status
call :is_running
if not errorlevel 1 (
  echo Server is RUNNING with PID !PID!.
  exit /b 0
)
echo Server is STOPPED.
exit /b 0

:logs
if not exist "%LOG_FILE%" (
  echo Log file not found: %LOG_FILE%
  echo Has the server been started at least once?
  exit /b 1
)
echo Tailing logs from %LOG_FILE%... (Press Ctrl+C to stop)
powershell -NoProfile -Command "Get-Content -Path '%LOG_FILE%' -Wait"
exit /b 0
