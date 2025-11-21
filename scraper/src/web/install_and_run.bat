@echo off
REM Install dependencies and run the web viewer

REM Change to the script's directory
cd /d "%~dp0"

echo ========================================
echo BPO Intelligence Web Viewer
echo ========================================
echo.
echo Current directory: %CD%
echo.

REM Check if requirements.txt exists
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found!
    echo Expected location: %CD%\requirements.txt
    echo.
    pause
    exit /b 1
)

echo Step 1: Installing dependencies...
echo Installing from: %CD%\requirements.txt
echo.

REM Try to install asyncpg with pre-built wheel first
echo Attempting to install asyncpg (this may take a moment)...
pip install --only-binary :all: asyncpg 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: Could not install pre-built asyncpg wheel.
    echo This usually means you need Microsoft C++ Build Tools.
    echo.
    echo Attempting to install all dependencies (may require build tools)...
    echo.
)

pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ========================================
    echo ERROR: Failed to install dependencies!
    echo ========================================
    echo.
    echo The issue is likely with 'asyncpg' which requires:
    echo   Microsoft Visual C++ 14.0 or greater
    echo.
    echo Solutions:
    echo   1. Install Microsoft C++ Build Tools:
    echo      https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo.
    echo   2. OR use Python 3.11 or 3.12 (which have pre-built wheels)
    echo      Current Python version may not have pre-built wheels
    echo.
    echo   3. OR try installing asyncpg separately:
    echo      pip install asyncpg --only-binary :all:
    echo.
    pause
    exit /b 1
)

echo.
echo Step 2: Testing setup...
if exist "test_setup.py" (
    python test_setup.py
) else (
    echo WARNING: test_setup.py not found, skipping test...
)
if errorlevel 1 (
    echo.
    echo WARNING: Some tests failed. The viewer may not work correctly.
    echo.
    pause
)

echo.
echo Step 3: Starting web viewer...
if not exist "run.py" (
    echo ERROR: run.py not found!
    echo Expected location: %CD%\run.py
    echo.
    pause
    exit /b 1
)

echo.
echo The viewer will be available at:
echo   - http://localhost:8000
echo   - http://127.0.0.1:8000
echo.
echo Press CTRL+C to stop the server
echo.
echo ========================================
echo.

python run.py

pause

