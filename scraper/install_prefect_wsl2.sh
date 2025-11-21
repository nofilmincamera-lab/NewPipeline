#!/bin/bash
# Install and Configure Prefect Server in WSL2
#
# This script installs Prefect Server to run natively in WSL2 instead of Docker.
# The server will connect to PostgreSQL running in Docker.

set -e

echo "=========================================="
echo "Prefect Server WSL2 Installation"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PREFECT_VERSION="3.1.9"
PREFECT_PORT="4200"
PREFECT_DATA_DIR="$HOME/.prefect"
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_DB="bpo_intelligence"
POSTGRES_USER="bpo_user"
POSTGRES_PASSWORD="bpo_secure_password_2025"

echo -e "${GREEN}[1/6]${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 not found. Please install Python 3.11+ first.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "  Python version: $(python3 --version)"

echo -e "${GREEN}[2/6]${NC} Installing Prefect ${PREFECT_VERSION}..."
pip3 install --user "prefect==${PREFECT_VERSION}" || {
    echo -e "${YELLOW}Warning: pip3 install failed, trying with sudo...${NC}"
    sudo pip3 install "prefect==${PREFECT_VERSION}"
}

# Add user local bin to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "  Adding ~/.local/bin to PATH..."
    export PATH="$HOME/.local/bin:$PATH"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
fi

echo -e "${GREEN}[3/6]${NC} Verifying Prefect installation..."
if ! command -v prefect &> /dev/null; then
    echo -e "${RED}ERROR: prefect command not found.${NC}"
    echo "  Try: source ~/.bashrc"
    exit 1
fi

PREFECT_VERSION_INSTALLED=$(prefect version)
echo "  Installed: $PREFECT_VERSION_INSTALLED"

echo -e "${GREEN}[4/6]${NC} Creating Prefect data directory..."
mkdir -p "$PREFECT_DATA_DIR"
echo "  Data directory: $PREFECT_DATA_DIR"

echo -e "${GREEN}[5/6]${NC} Testing PostgreSQL connection..."
# Check if PostgreSQL is accessible
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}Warning: psql not found. Installing postgresql-client...${NC}"
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

echo -e "${GREEN}[6/6]${NC} Creating startup script..."

# Create startup script
STARTUP_SCRIPT="$HOME/start_prefect_server.sh"
cat > "$STARTUP_SCRIPT" << EOF
#!/bin/bash
# Start Prefect Server
# This script starts Prefect Server with PostgreSQL backend

export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
export PREFECT_SERVER_API_HOST="0.0.0.0"
export PREFECT_API_URL="http://0.0.0.0:${PREFECT_PORT}/api"
export PREFECT_HOME="$PREFECT_DATA_DIR"

echo "Starting Prefect Server..."
echo "  API URL: http://localhost:${PREFECT_PORT}/api"
echo "  UI: http://localhost:${PREFECT_PORT}"
echo "  Database: ${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo ""
echo "Press Ctrl+C to stop"
echo ""

prefect server start --host 0.0.0.0
EOF

chmod +x "$STARTUP_SCRIPT"
echo "  Created: $STARTUP_SCRIPT"

# Create systemd service file (optional)
SYSTEMD_SERVICE="$HOME/.config/systemd/user/prefect-server.service"
mkdir -p "$(dirname "$SYSTEMD_SERVICE")"
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
# Memory settings - Prefect Server can use up to 4GB
Environment="PYTHONUNBUFFERED=1"
ExecStart=$(which prefect) server start --host 0.0.0.0
Restart=always
RestartSec=10
# Memory limit (optional, remove if you want unlimited)
# LimitNOFILE=65536

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
echo "  python3 scraper/check_prefect_server.py"
echo ""

