@echo off
setlocal enabledelayedexpansion

rem This script builds the Gerrit MCP server by setting up its Python environment.

set "SERVER_DIR=."
set "REQUIREMENTS_FILE=requirements.txt"
set "VENV_DIR=.venv"
set "UV_REQUIREMENTS=uv-requirements.txt"

echo.
echo Setting up the Python environment for the Gerrit MCP server...

if not exist "build" mkdir "build"

echo Creating virtual environment in %VENV_DIR%...
python -m venv "%VENV_DIR%"
if errorlevel 1 (
  echo Failed to create virtual environment.
  exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
  echo Failed to activate virtual environment.
  exit /b 1
)

echo Installing uv...
pip install -r "%UV_REQUIREMENTS%" --require-hashes
if errorlevel 1 (
  echo Failed to install uv.
  exit /b 1
)

echo Compiling dependencies and generating hashes...
uv pip compile pyproject.toml --generate-hashes --output-file %REQUIREMENTS_FILE% --extra dev --extra-index-url https://pypi.org/simple
if errorlevel 1 (
  echo Failed to compile dependencies.
  exit /b 1
)

echo Installing dependencies from %REQUIREMENTS_FILE%...
uv pip sync %REQUIREMENTS_FILE%
if errorlevel 1 (
  echo Failed to set up the Python environment.
  exit /b 1
)

echo Building and installing the gerrit_mcp_server package...
uv build
if errorlevel 1 (
  echo Failed to build the gerrit_mcp_server package.
  exit /b 1
)

for /f "delims=" %%F in ('dir /b /a:-d dist\*.whl') do (
  set "WHEEL_FILE=dist\%%F"
  goto :gotwheel
)
echo Failed to locate built wheel in dist\.
exit /b 1

:gotwheel
for /f "usebackq tokens=1" %%H in (`certutil -hashfile "!WHEEL_FILE!" SHA256 ^| find /i /v "hash" ^| find /i /v "certutil"`) do (
  set "WHEEL_HASH=%%H"
  goto :gothash
)
echo Failed to compute wheel hash.
exit /b 1

:gothash
echo !WHEEL_FILE! --hash=sha256:!WHEEL_HASH!> local-requirements.txt

uv pip install -r local-requirements.txt --no-deps --require-hashes
if errorlevel 1 (
  echo Failed to install the gerrit_mcp_server package.
  del local-requirements.txt
  exit /b 1
)

del local-requirements.txt

echo.
echo Successfully set up the Gerrit MCP server environment.
exit /b 0
