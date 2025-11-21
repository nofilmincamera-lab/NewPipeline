# Prefect Server WSL2 Installation Guide

Prefect Server has been moved from Docker to run natively in WSL2 for better performance and easier management.

## Prerequisites

1. **WSL2** installed and configured
2. **Python 3.11+** installed in WSL2
3. **PostgreSQL** running in Docker (accessible at `localhost:5432`)

## Installation Steps

### 1. Install Prefect Server

From WSL2, navigate to the scraper directory and run:

```bash
cd /mnt/c/Users/nofil/OneDrive/Documents/GitHub/NewPipeline/scraper
bash install_prefect_wsl2.sh
```

This script will:
- Install Prefect 3.1.9
- Verify PostgreSQL connection
- Create startup scripts
- Create systemd service (optional)

### 2. Start Prefect Server

#### Option A: Manual Start (Recommended for testing)

```bash
bash start_prefect_wsl2.sh
```

#### Option B: Using the generated startup script

```bash
~/start_prefect_server.sh
```

#### Option C: Systemd Service (Recommended for production)

```bash
# Enable and start the service
systemctl --user enable prefect-server
systemctl --user start prefect-server

# Check status
systemctl --user status prefect-server

# View logs
journalctl --user -u prefect-server -f
```

### 3. Verify Installation

From Windows or WSL2:

```bash
# Check server health
curl http://localhost:4200/health

# Or use the Python checker
python3 scraper/check_prefect_server.py
```

### 4. Access Prefect UI

Open in your browser:
- **Prefect UI**: http://localhost:4200
- **API**: http://localhost:4200/api

## Configuration

The Prefect Server connects to PostgreSQL running in Docker using:
- **Host**: `localhost` (Docker port forwarding)
- **Port**: `5432`
- **Database**: `bpo_intelligence`
- **User**: `bpo_user`
- **Password**: From `ops/secrets/postgres_password.txt`

## Docker Integration

The `scraper-core` Docker container connects to Prefect Server using:
- **URL**: `http://host.docker.internal:4200/api`

This allows the container to access the Prefect Server running on the WSL2 host.

## Troubleshooting

### Prefect Server Won't Start

1. **Check PostgreSQL is running**:
   ```bash
   docker ps | grep postgres
   ```

2. **Test PostgreSQL connection**:
   ```bash
   psql -h localhost -p 5432 -U bpo_user -d bpo_intelligence
   ```

3. **Check Prefect logs**:
   ```bash
   # If using systemd
   journalctl --user -u prefect-server -n 50
   
   # If running manually, check terminal output
   ```

### Port 4200 Already in Use

```bash
# Find process using port 4200
sudo lsof -i :4200

# Kill the process
sudo kill -9 <PID>
```

### Cannot Connect from Docker Container

Ensure `host.docker.internal` is accessible. On some systems, you may need to use the WSL2 IP address instead:

```bash
# Get WSL2 IP address
ip addr show eth0 | grep inet

# Update docker-compose.yml PREFECT_API_URL to use the IP
```

## Stopping Prefect Server

### Manual Process
Press `Ctrl+C` in the terminal where it's running.

### Systemd Service
```bash
systemctl --user stop prefect-server
systemctl --user disable prefect-server
```

## Data Persistence

Prefect data is stored in:
- **Location**: `~/.prefect/` (in WSL2 home directory)
- **Backup**: Consider backing up this directory periodically

## Migration Notes

- The Prefect Server Docker container has been removed from `docker-compose.yml`
- Existing Prefect data in `../data/prefect/` can be migrated to `~/.prefect/` if needed
- The `scraper-core` container now connects to WSL2-hosted Prefect Server

