#!/bin/bash

# Setup script for CF Tunnel Manager (PyQt version)

echo "Setting up CF Tunnel Manager..."

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "python3 is not installed. Please install Python 3 first."
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install required packages
echo "Installing required packages..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Failed to install requirements. Trying with --break-system-packages flag..."
    pip install --break-system-packages -r requirements.txt
fi

if [ $? -ne 0 ]; then
    echo "Failed to install requirements. You may need to install PySide6 through your system package manager:"
    echo "For openSUSE: sudo zypper install python313-PySide6"
    exit 1
fi

echo "Setup completed successfully!"
echo ""
echo "To run the application:"
echo "  source venv/bin/activate && python3 main.py"
echo ""
echo "Or use the run script:"
echo "  ./run.sh"
echo ""
echo "To create an RPM package for openSUSE:"
echo "  ./create_rpm.sh"