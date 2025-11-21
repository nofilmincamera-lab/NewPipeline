# Troubleshooting Guide

## asyncpg Installation Error (C++ Build Tools Required)

### Error Message:
```
error: Microsoft Visual C++ 14.0 or greater is required
```

### Solutions:

#### Option 1: Install Microsoft C++ Build Tools (Recommended)
1. Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Install "Desktop development with C++" workload
3. Run the installation script again

#### Option 2: Use Python 3.11 or 3.12
Python 3.13 is very new and may not have pre-built wheels for asyncpg.
- Download Python 3.11 or 3.12 from python.org
- Create a virtual environment with that version
- Install dependencies again

#### Option 3: Install asyncpg separately
```bash
# Try to get pre-built wheel
pip install --only-binary :all: asyncpg

# If that fails, install build tools and try again
pip install asyncpg
```

#### Option 4: Use alternative database driver (if you don't need asyncpg)
You could modify the code to use `psycopg2` instead, but this requires more code changes.

## Quick Fix Script

Run `install_dependencies.bat` which has better error handling:
```bash
cd scraper/src/web
install_dependencies.bat
```

## Check Your Python Version

```bash
python --version
```

If you're on Python 3.13, consider using Python 3.11 or 3.12 for better compatibility.

## Verify Installation

After installing dependencies, test:
```bash
python test_setup.py
```

This will tell you what's missing.

