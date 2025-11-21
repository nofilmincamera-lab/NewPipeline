#!/bin/bash
# Linux/Mac script to start the web viewer

echo "Installing/updating dependencies..."
pip install -r requirements.txt

echo ""
echo "Starting web viewer..."
python run.py

