# TunnelFlare

A modern, high-fidelity GUI for managing Cloudflare Tunnels on Linux. Designed for a seamless development experience with a focus on speed and visual clarity.

## Features

- **Tunnel Management**: Create, start, stop, and delete tunnels through an intuitive interface.
- **Real-time Monitoring**: Integrated live log viewer and status indicators.
- **Quick Actions**: One-click URL copying, browser access, and QR code generation for mobile testing.
- **Desktop Integration**: Full system tray support and AppImage distribution.

## Visuals

![App Home Screen](./screenshots/home.png)
*Home Screen showcasing active environments.*

![Tunnel Details](./screenshots/details.png)
*Detailed view with logs and action controls.*

## Installation

### AppImage (Recommended)
Download the latest `TunnelFlare-x86_64.AppImage` from the releases page and run:
```bash
chmod +x TunnelFlare-x86_64.AppImage
./TunnelFlare-x86_64.AppImage
```

### Development Setup
Requirements: Python 3.8+, Cloudflared CLI.
```bash
git clone https://github.com/madroots/TunnelFlare
cd TunnelFlare
./setup.sh
./run.sh
```

## Configuration
Application data and tunnel configurations are stored in `~/.tunnelflare`.
