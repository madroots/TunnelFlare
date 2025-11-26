#!/bin/bash

# Development script to start CF Tunnel Manager GUI
# Activates virtual environment and runs the application

cd "$(dirname "$0")/pyqt_app"

if [ ! -d "venv" ]; then
    echo "Virtual environment not found!"
    echo "Please run setup.sh first to create the virtual environment"
    echo "cd pyqt_app && ./setup.sh"
    exit 1
fi

echo "Activating virtual environment and starting CF Tunnel Manager..."
source venv/bin/activate
python3 main.py