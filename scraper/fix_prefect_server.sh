#!/bin/bash
# Fix Prefect Server Database Connection
# This script helps set up the Prefect server with proper password configuration

set -e

echo "=========================================="
echo "Prefect Server Configuration Fix"
echo "=========================================="

# Check if POSTGRES_PASSWORD is set
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "WARNING: POSTGRES_PASSWORD environment variable is not set"
    echo ""
    echo "Option 1: Set environment variable:"
    echo "  export POSTGRES_PASSWORD='your_password'"
    echo "  docker-compose restart prefect-server"
    echo ""
    echo "Option 2: Use secret file (default):"
    echo "  Ensure ../ops/secrets/postgres_password.txt exists"
    echo ""
    
    # Check if secret file exists
    SECRET_FILE="../ops/secrets/postgres_password.txt"
    if [ -f "$SECRET_FILE" ]; then
        echo "[OK] Secret file found: $SECRET_FILE"
        echo "The Prefect server should use this file automatically."
    else
        echo "[ERROR] Secret file not found: $SECRET_FILE"
        echo "Please create it or set POSTGRES_PASSWORD environment variable"
        exit 1
    fi
else
    echo "[OK] POSTGRES_PASSWORD environment variable is set"
    echo "The Prefect server will use this value."
fi

echo ""
echo "Restarting Prefect server..."
docker-compose -f scraper/docker-compose.yml restart prefect-server

echo ""
echo "Waiting for server to start..."
sleep 5

echo ""
echo "Checking Prefect server status..."
docker logs bpo-prefect-server --tail 20

echo ""
echo "=========================================="
echo "Check Prefect UI at: http://localhost:4200"
echo "=========================================="

