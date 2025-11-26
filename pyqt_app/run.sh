#!/bin/bash

# Run script for CF Tunnel Manager

if [ -d "venv" ]; then
    source venv/bin/activate
    python3 main.py "$@"
else
    echo "Virtual environment not found. Please run setup.sh first."
    echo "Or install PySide6 and run directly: python3 main.py"
fi