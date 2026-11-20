@echo off
setlocal
cd /d "%~dp0"
echo -----------------------------------------
echo    TunnelFlare Windows Setup Wizard
echo -----------------------------------------
echo.

:: Check for Python 3.11+
python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 (
    echo Error: Python 3.11 or newer is required and must be in PATH.
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv .venv
if errorlevel 1 goto :fail

echo Installing locked dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install --require-hashes -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo -----------------------------------------
echo    Installation Complete!
echo    Use run.bat to start TunnelFlare.
echo -----------------------------------------
pause
exit /b 0

:fail
echo.
echo Installation failed. See the messages above.
pause
exit /b 1
