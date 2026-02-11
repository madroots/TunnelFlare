# TunnelFlare

A modern, high-fidelity GUI for managing Cloudflare Tunnels on Linux. Designed for a seamless development experience with a focus on speed and visual clarity.

## Features

- **Tunnel Management**: Create, start, stop, and delete tunnels through an intuitive interface.
- **Real-time Monitoring**: Integrated live log viewer and status indicators.
- **Quick Actions**: One-click URL copying, browser access, and QR code generation for mobile testing.
- **Desktop Integration**: Full system tray support and AppImage distribution.

## Visuals

<table border="0" style="border: none; border-collapse: collapse;">
  <tr>
    <td style="border: none;">
      <img width="425" alt="Home Screen" src="https://github.com/user-attachments/assets/721ee374-ad05-4706-b531-7a670ec91fa5"><br>
      <i>Home Screen showcasing active environments.</i>
    </td>
    <td style="border: none;">
      <img width="425" alt="Detailed View" src="https://github.com/user-attachments/assets/aaa79aeb-3ee8-4719-9dd2-c6d63c17618f"><br>
      <i>Detailed view with logs and action controls.</i>
    </td>
  </tr>
</table>

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
