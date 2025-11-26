# TunnelFlare - CF Tunnel Manager

A farily modern GUI application for managing Cloudflare tunnels, built with Python and Qt.

## Overview

CF Tunnel Manager provides a graphical interface for managing Cloudflare tunnels, allowing you to:
- View all running tunnels with their details
- Start new tunnels with custom names, ports, and protocols
- Stop individual tunnels or all tunnels at once
- View tunnel logs in real-time
- Access through system tray for convenience

## Requirements

- Python 3.7+
- Cloudflared (must be installed and in your PATH)

## Quick Start

1. Install Cloudflared if not already installed:
   ```bash
   sudo zypper install cloudflared
   # Or download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation
   ```

2. Navigate to the pyqt_app directory and set up the virtual environment:
   ```bash
   cd pyqt_app
   ./setup.sh
   ```

3. Run the application:
   ```bash
   ./run.sh
   # Or for development: ./start_dev.sh
   ```

## Features

- Modern GUI built with PySide6
- System tray integration for quick access
- Multi-tunnel management (run multiple tunnels simultaneously)
- Real-time log viewing
- Easy start/stop controls
- Automatic cleanup of dead tunnels
