# CF Tunnel Manager

A modern GUI application for managing Cloudflare tunnels, built with Python and Qt.

## Overview

This project provides a modern graphical interface for the original Cloudflare tunnel manager shell script. It features:
- View all running tunnels with their details
- Start new tunnels with custom names, ports, and protocols
- Stop individual tunnels or all tunnels at once
- View tunnel logs in real-time
- System tray integration for quick access
- Modern, responsive UI

## Requirements

- Python 3.7+
- Cloudflared (must be installed and in your PATH)

## Quick Start

To run the development version:
```bash
./start_dev.sh
```

This will activate the virtual environment and start the GUI application.

## Project Structure

- `pyqt_app/` - Main PyQt application
- `source_script.sh` - Original bash script (for reference)
- `start_dev.sh` - Development startup script

## Installation

1. Install Cloudflared if not already installed:
   ```bash
   sudo zypper install cloudflared
   # Or download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation
   ```

2. Navigate to the pyqt_app directory:
   ```bash
   cd pyqt_app
   ```

3. Set up the virtual environment:
   ```bash
   ./setup.sh
   ```

4. Run the application:
   ```bash
   ./run.sh
   ```

## Packaging

To create an RPM package for openSUSE:
```bash
cd pyqt_app
./create_rpm.sh
```