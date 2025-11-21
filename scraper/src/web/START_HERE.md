# START HERE - Web Viewer Quick Start

## 🚀 Easiest Way to Start (Windows)

**Just double-click:** `install_and_run.bat`

This will:
1. ✅ Install all required dependencies
2. ✅ Test the setup
3. ✅ Start the web viewer

### ⚠️ IMPORTANT: If you get a C++ Build Tools error

If you see: `error: Microsoft Visual C++ 14.0 or greater is required`

**Quick Fix Options:**
1. **Install C++ Build Tools** (takes ~5 minutes):
   - Download: https://visualstudio.microsoft.com/visual-cpp-build-tools/
   - Install "Desktop development with C++" workload
   - Run `install_and_run.bat` again

2. **OR use Python 3.11 or 3.12** (has pre-built packages):
   - Python 3.13 may not have pre-built wheels yet
   - Download from python.org

3. **OR try the dependency installer first:**
   - Run `install_dependencies.bat` (has better error handling)

## 📍 Where to Access the Viewer

Once started, the viewer is available at:

- **http://localhost:8000** ← Use this one!
- **http://127.0.0.1:8000** ← Alternative
- **http://0.0.0.0:8000** ← Not a valid browser URL (this is the bind address)

**Note:** The server binds to `0.0.0.0:8000` which means:
- ✅ Works on `localhost:8000` (recommended)
- ✅ Works on `127.0.0.1:8000`
- ✅ Also accessible from other devices on your network at `http://YOUR_COMPUTER_IP:8000`

## 🔧 Manual Installation

If the batch file doesn't work:

```bash
# 1. Navigate to web directory
cd scraper/src/web

# 2. Install dependencies
pip install -r requirements.txt

# 3. Test setup (optional)
python test_setup.py

# 4. Run the viewer
python run.py
```

## ❌ Common Issues

### "ModuleNotFoundError: No module named 'fastapi'"
**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
```

### "Could not connect to database"
**Solution:** 
1. Make sure PostgreSQL is running
2. Check database exists: `bpo_intelligence`
3. Check user exists: `bpo_user`
4. Password file at: `ops/secrets/postgres_password.txt` (or uses default "postgres")

### Port 8000 already in use
**Solution:** Change port in `run.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8080)  # Use port 8080 instead
```

### Can't access from browser
**Solution:** 
- Make sure you're using `http://localhost:8000` (not `https://`)
- Check Windows Firewall isn't blocking port 8000
- Try `http://127.0.0.1:8000` instead

## 📊 What You'll See

- **Home Page:** List of all organizations with search
- **Organization Detail:** Complete profile with products, services, certifications, etc.
- **Corporate Entities:** View entity hierarchies
- **Statistics:** Database statistics and breakdowns

## 🆘 Still Not Working?

1. Run the test script: `python test_setup.py`
2. Check the logs: Look for `web_viewer.log` file
3. Check health endpoint: Visit `http://localhost:8000/health` (once server is running)

