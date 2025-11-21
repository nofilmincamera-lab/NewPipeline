# Install Prefect Server in WSL - Quick Guide

## Prerequisites

1. WSL2 installed with Ubuntu (or another Linux distribution)
2. PostgreSQL running in Docker (accessible at `localhost:5432`)

## Installation Location

**Prefect is installed outside OneDrive** to avoid sync issues:
- **Prefect Data**: `~/prefect-data` (in WSL home directory)
- **Prefect Binary**: `~/.local/bin/prefect` (standard user install location)
- **Password File**: `~/.prefect-postgres-password` (local copy, outside OneDrive)

## Installation Steps

### Step 1: Open WSL Terminal

Open your WSL terminal (Ubuntu or your preferred distribution).

### Step 2: Navigate to Project Directory

```bash
# If your project is in Windows, use the /mnt/c path
cd /mnt/c/Users/nofil/OneDrive/Documents/GitHub/NewPipeline/scraper

# Or if you've cloned it in WSL's home directory
# cd ~/NewPipeline/scraper
```

### Step 3: Make Script Executable

```bash
chmod +x install_prefect_wsl.sh
```

### Step 4: Run Installation Script

```bash
bash install_prefect_wsl.sh
```

The script will:
- Check Python installation
- Install Prefect 3.1.9
- Verify PostgreSQL connection
- Create startup scripts
- Create systemd service (optional)

### Step 5: Start Prefect Server

After installation, start the server:

```bash
# Option 1: Use the generated startup script
~/start_prefect_server.sh

# Option 2: Start manually
export PATH="$HOME/.local/bin:$PATH"
export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://bpo_user:YOUR_PASSWORD@localhost:5432/bpo_intelligence"
export PREFECT_SERVER_API_HOST="0.0.0.0"
export PREFECT_API_URL="http://0.0.0.0:4200/api"
export PREFECT_HOME="$HOME/.prefect"
prefect server start --host 0.0.0.0
```

### Step 6: Verify Installation

In a new terminal (Windows or WSL):

```bash
# Check server health
curl http://localhost:4200/health

# Or use Python checker
python3 scraper/check_prefect_server.py
```

## Access Prefect UI

Open in your browser:
- **Prefect UI**: http://localhost:4200
- **API**: http://localhost:4200/api

## Troubleshooting

### Prefect Command Not Found

```bash
# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Make permanent
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### PostgreSQL Connection Failed

1. Make sure Docker containers are running:
   ```bash
   docker ps | grep postgres
   ```

2. Test connection:
   ```bash
   psql -h localhost -p 5432 -U bpo_user -d bpo_intelligence
   ```

3. Check password in secret file:
   ```bash
   cat ../ops/secrets/postgres_password.txt
   ```

### Port 4200 Already in Use

```bash
# Find process using port 4200
sudo lsof -i :4200

# Kill the process
sudo kill -9 <PID>
```

### Python Not Found

```bash
# Install Python 3.11+
sudo apt-get update
sudo apt-get install -y python3 python3-pip
```

## Running as Systemd Service (Optional)

To run Prefect Server as a background service:

```bash
# Enable the service
systemctl --user enable prefect-server

# Start the service
systemctl --user start prefect-server

# Check status
systemctl --user status prefect-server

# View logs
journalctl --user -u prefect-server -f

# Stop the service
systemctl --user stop prefect-server
```

## Manual Installation (If Script Fails)

If the script doesn't work, install manually:

```bash
# 1. Install Prefect
pip3 install --user prefect==3.1.9

# 2. Add to PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# 3. Verify installation
prefect version

# 4. Set environment variables
export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://bpo_user:YOUR_PASSWORD@localhost:5432/bpo_intelligence"
export PREFECT_SERVER_API_HOST="0.0.0.0"
export PREFECT_API_URL="http://0.0.0.0:4200/api"
export PREFECT_HOME="$HOME/.prefect"

# 5. Start server
prefect server start --host 0.0.0.0
```

## Next Steps

After Prefect Server is running:

1. Verify it's accessible: http://localhost:4200
2. Check logs if there are any issues
3. Configure your scraping workflows to use the Prefect API

