#!/bin/bash
# Install Prefect Server in WSL
# This script should be run from within WSL

set -e

echo "=========================================="
echo "Prefect Server WSL Installation"
echo "=========================================="

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PREFECT_VERSION="3.1.9"
PREFECT_PORT="4200"
# Install Prefect data outside OneDrive - use WSL home directory
PREFECT_DATA_DIR="$HOME/prefect-data"
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_DB="bpo_intelligence"
POSTGRES_USER="bpo_user"

# Try to get password from secret file (in OneDrive project)
SECRET_FILE="$SCRIPT_DIR/../ops/secrets/postgres_password.txt"
# Also create a local copy outside OneDrive for easier access
LOCAL_SECRET_FILE="$HOME/.prefect-postgres-password"

if [ -f "$SECRET_FILE" ]; then
    POSTGRES_PASSWORD=$(cat "$SECRET_FILE" | tr -d '\n\r')
    # Copy password to local file outside OneDrive
    echo "$POSTGRES_PASSWORD" > "$LOCAL_SECRET_FILE"
    chmod 600 "$LOCAL_SECRET_FILE"
    echo -e "${GREEN}Using password from secret file${NC}"
    echo -e "${GREEN}  Copied to local file: $LOCAL_SECRET_FILE${NC}"
else
    POSTGRES_PASSWORD="bpo_secure_password_2025"
    echo -e "${YELLOW}Warning: Secret file not found, using default password${NC}"
fi

echo -e "${GREEN}[1/7]${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 not found. Please install Python 3.11+ first.${NC}"
    echo "  Install with: sudo apt-get update && sudo apt-get install -y python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "  $PYTHON_VERSION"

echo -e "${GREEN}[2/7]${NC} Checking pip installation..."
if ! command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}pip3 not found. Installing...${NC}"
    sudo apt-get update && sudo apt-get install -y python3-pip
fi

echo -e "${GREEN}[3/7]${NC} Installing Prefect ${PREFECT_VERSION}..."
# Try user install first
if pip3 install --user "prefect==${PREFECT_VERSION}"; then
    echo -e "${GREEN}  Prefect installed successfully${NC}"
else
    echo -e "${YELLOW}User install failed, trying with sudo...${NC}"
    sudo pip3 install "prefect==${PREFECT_VERSION}"
fi

# Add user local bin to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "  Adding ~/.local/bin to PATH..."
    export PATH="$HOME/.local/bin:$PATH"
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' ~/.bashrc 2>/dev/null; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    fi
fi

echo -e "${GREEN}[4/7]${NC} Verifying Prefect installation..."
# Source bashrc to get updated PATH
source ~/.bashrc 2>/dev/null || true
export PATH="$HOME/.local/bin:$PATH"

if ! command -v prefect &> /dev/null; then
    echo -e "${RED}ERROR: prefect command not found.${NC}"
    echo "  Try: source ~/.bashrc"
    echo "  Or: export PATH=\"\$HOME/.local/bin:\$PATH\""
    exit 1
fi

PREFECT_VERSION_INSTALLED=$(prefect version 2>&1 || echo "unknown")
echo "  Installed: $PREFECT_VERSION_INSTALLED"

echo -e "${GREEN}[5/7]${NC} Creating Prefect data directory..."
mkdir -p "$PREFECT_DATA_DIR"
echo "  Data directory: $PREFECT_DATA_DIR"

echo -e "${GREEN}[6/7]${NC} Testing PostgreSQL connection..."
# Check if PostgreSQL is accessible
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}psql not found. Installing postgresql-client...${NC}"
    sudo apt-get update && sudo apt-get install -y postgresql-client
fi

# Test connection
export PGPASSWORD="$POSTGRES_PASSWORD"
if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" &> /dev/null; then
    echo -e "${GREEN}  PostgreSQL connection successful!${NC}"
else
    echo -e "${YELLOW}Warning: Could not connect to PostgreSQL.${NC}"
    echo "  Make sure Docker containers are running:"
    echo "    cd scraper && docker-compose up -d postgres"
    echo "  Connection details:"
    echo "    Host: $POSTGRES_HOST"
    echo "    Port: $POSTGRES_PORT"
    echo "    Database: $POSTGRES_DB"
    echo "    User: $POSTGRES_USER"
fi
unset PGPASSWORD

echo -e "${GREEN}[7/7]${NC} Creating startup script..."

# Create startup script
STARTUP_SCRIPT="$HOME/start_prefect_server.sh"
cat > "$STARTUP_SCRIPT" << EOF
#!/bin/bash
# Start Prefect Server
# This script starts Prefect Server with PostgreSQL backend

# Load password from local file (outside OneDrive) or fallback to project file
LOCAL_SECRET_FILE="\$HOME/.prefect-postgres-password"
PROJECT_SECRET_FILE="$SCRIPT_DIR/../ops/secrets/postgres_password.txt"

if [ -f "\$LOCAL_SECRET_FILE" ]; then
    POSTGRES_PASSWORD=\$(cat "\$LOCAL_SECRET_FILE" | tr -d '\n\r')
elif [ -f "\$PROJECT_SECRET_FILE" ]; then
    POSTGRES_PASSWORD=\$(cat "\$PROJECT_SECRET_FILE" | tr -d '\n\r')
else
    POSTGRES_PASSWORD="bpo_secure_password_2025"
fi

export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://${POSTGRES_USER}:\${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
export PREFECT_SERVER_API_HOST="0.0.0.0"
export PREFECT_API_URL="http://0.0.0.0:${PREFECT_PORT}/api"
export PREFECT_HOME="$PREFECT_DATA_DIR"

# Ensure Prefect is in PATH
export PATH="\$HOME/.local/bin:\$PATH"

echo "=========================================="
echo "Starting Prefect Server"
echo "=========================================="
echo "API URL: http://localhost:${PREFECT_PORT}/api"
echo "UI: http://localhost:${PREFECT_PORT}"
echo "Database: ${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

prefect server start --host 0.0.0.0
EOF

chmod +x "$STARTUP_SCRIPT"
echo "  Created: $STARTUP_SCRIPT"

# Create systemd service file (optional)
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"
SYSTEMD_SERVICE="$SYSTEMD_DIR/prefect-server.service"

cat > "$SYSTEMD_SERVICE" << EOF
[Unit]
Description=Prefect Server
After=network.target

[Service]
Type=simple
User=$USER
Environment="PREFECT_API_DATABASE_CONNECTION_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
Environment="PREFECT_SERVER_API_HOST=0.0.0.0"
Environment="PREFECT_API_URL=http://0.0.0.0:${PREFECT_PORT}/api"
Environment="PREFECT_HOME=$PREFECT_DATA_DIR"
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$HOME/.local/bin/prefect server start --host 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

echo "  Created systemd service: $SYSTEMD_SERVICE"
echo "  To enable: systemctl --user enable prefect-server"
echo "  To start: systemctl --user start prefect-server"

echo ""
echo "=========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "To start Prefect Server:"
echo "  1. Manual: $STARTUP_SCRIPT"
echo "  2. Systemd: systemctl --user start prefect-server"
echo ""
echo "Prefect UI will be available at:"
echo "  http://localhost:${PREFECT_PORT}"
echo ""
echo "To verify installation:"
echo "  python3 $SCRIPT_DIR/check_prefect_server.py"
echo ""

