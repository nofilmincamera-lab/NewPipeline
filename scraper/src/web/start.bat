@echo off
REM Windows batch script to start the web viewer

REM Change to the script's directory
cd /d "%~dp0"

echo Installing/updating dependencies...
if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    echo ERROR: requirements.txt not found in %CD%
    pause
    exit /b 1
)

echo.
echo Starting web viewer...
if exist "run.py" (
    python run.py
) else (
    echo ERROR: run.py not found in %CD%
    pause
    exit /b 1
)

pause

