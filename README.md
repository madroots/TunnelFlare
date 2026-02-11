# TunnelFlare

Expose local apps instantly and securely through Cloudflare tunnels — no account required. Turn localhost into a secure public URL with one click.

## Features
- **No Account Needed**: You don't need cloudflare account - create tunnels immediately with zero configuration.
- **Tunnel Management**: Create, start, stop, and delete tunnels through an intuitive interface.
- **Quick Actions**: One-click URL copying, browser access, and QR code generation for mobile testing.

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

## Quick Start

### Recommended: Gear Lever

**[Gear Lever](https://github.com/mijorus/gearlever)** is the recommended way to manage your AppImages.  
It seamlessly integrates them into your system menu and handles updates.

1. Download the latest `.AppImage` from the [Releases](https://github.com/madroots/TunnelFlare/releases) page.  
2. Drag & Drop `TunnelFlare.AppImage` into Gear Lever and click **Install/run**.


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
