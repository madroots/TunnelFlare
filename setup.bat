@echo off
echo -----------------------------------------
echo    TunnelFlare Windows Setup Wizard
echo -----------------------------------------
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv .venv

echo Activating environment and installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install .

echo.
echo -----------------------------------------
echo    Installation Complete!
echo    Use run.bat to start TunnelFlare.
echo -----------------------------------------
pause
