# CF Tunnel Manager (PyQt Version)

A modern GUI application for managing Cloudflare tunnels, built with Python and Qt.

## Features

- View all running tunnels with their details
- Start new tunnels with custom names, ports, and protocols
- Stop individual tunnels or all tunnels at once
- View tunnel logs in real-time
- System tray integration for quick access
- Modern, responsive UI

## Requirements

- Python 3.7+
- Cloudflared (must be installed and in your PATH)

## Installation

1. Install Cloudflared:
   ```bash
   # For openSUSE:
   sudo zypper install cloudflared
   # Or download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation
   ```

2. Set up the application:
   ```bash
   cd pyqt_app
   ./setup.sh
   ```

## Usage

Run the application:
```bash
cd pyqt_app
./run.sh
```

Or activate the virtual environment and run directly:
```bash
cd pyqt_app
source venv/bin/activate
python3 main.py
```

## Packaging for openSUSE

To create an RPM package:
```bash
cd pyqt_app
./create_rpm.sh
```

This will create an RPM file that can be installed on openSUSE systems.

## Functionality

The application replicates all functionality from the original bash script:

- **Tunnels Tab**: View, start, and stop tunnels
- **Logs Tab**: View tunnel logs in real-time
- **System Tray**: Quick access to common functions
- **Settings Tab**: Configuration options (to be implemented)

## Directory Structure

The application uses the same directory structure as the original script:
- `~/.cf-tunnels/` - Stores tunnel configuration files
- `~/.cf-tunnels/logs/` - Stores tunnel log files