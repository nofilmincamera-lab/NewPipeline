#!/bin/bash
# Quick start script for Prefect Server in WSL2

# Load PostgreSQL password from secret file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRET_FILE="$SCRIPT_DIR/../ops/secrets/postgres_password.txt"

if [ -f "$SECRET_FILE" ]; then
    POSTGRES_PASSWORD=$(cat "$SECRET_FILE" | tr -d '\n\r')
else
    POSTGRES_PASSWORD="bpo_secure_password_2025"
    echo "Warning: Secret file not found, using default password"
fi

# Configuration
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_DB="bpo_intelligence"
POSTGRES_USER="bpo_user"
PREFECT_PORT="4200"
PREFECT_DATA_DIR="$HOME/.prefect"

# Set environment variables
export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
export PREFECT_SERVER_API_HOST="0.0.0.0"
export PREFECT_API_URL="http://0.0.0.0:${PREFECT_PORT}/api"
export PREFECT_HOME="$PREFECT_DATA_DIR"

# Ensure Prefect is in PATH
export PATH="$HOME/.local/bin:$PATH"

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

# Check if prefect is installed
if ! command -v prefect &> /dev/null; then
    echo "ERROR: Prefect not found. Please run install_prefect_wsl2.sh first"
    exit 1
fi

# Start Prefect server
prefect server start --host 0.0.0.0

