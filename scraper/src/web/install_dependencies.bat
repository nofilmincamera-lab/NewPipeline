@echo off
REM Install dependencies with better error handling for asyncpg

cd /d "%~dp0"

echo ========================================
echo Installing Web Viewer Dependencies
echo ========================================
echo.

REM Check Python version
python --version
echo.

REM Try installing asyncpg first with pre-built wheel
echo Step 1: Installing asyncpg (database driver)...
echo This may require Microsoft C++ Build Tools if no pre-built wheel is available.
echo.

pip install --upgrade pip
echo.

REM Try pre-built wheel first
pip install --only-binary :all: asyncpg
if errorlevel 1 (
    echo.
    echo Pre-built wheel not available. Trying to build from source...
    echo This requires Microsoft C++ Build Tools.
    echo.
    pip install asyncpg
    if errorlevel 1 (
        echo.
        echo ========================================
        echo FAILED: asyncpg installation failed
        echo ========================================
        echo.
        echo You need Microsoft Visual C++ 14.0 or greater.
        echo.
        echo Download from:
        echo   https://visualstudio.microsoft.com/visual-cpp-build-tools/
        echo.
        echo OR use Python 3.11 or 3.12 which have pre-built wheels.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Step 2: Installing other dependencies...
pip install fastapi uvicorn jinja2 python-multipart loguru

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install some dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS: All dependencies installed!
echo ========================================
echo.
echo You can now run the viewer with:
echo   python run.py
echo.
pause

