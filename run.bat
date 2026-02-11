@echo off
set SCRIPT_DIR=%~dp0
if not exist "%SCRIPT_DIR%.venv" (
    echo Virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
python "%SCRIPT_DIR%main.py"
if %ERRORLEVEL% neq 0 pause
