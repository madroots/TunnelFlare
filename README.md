# TunnelFlare

Expose local apps instantly and securely through Cloudflare tunnels — no account required. Turn localhost into a secure public URL with one click.

## Features
- **No Account Needed**: You don't need a Cloudflare account. Create tunnels immediately with zero configuration.
- **Tunnel Management**: Create, edit, start, stop and delete tunnels. The status shows when a tunnel is starting, online or reconnecting.
- **Works with dev servers**: HTTPS local servers (self-signed certificates are fine), and an option to send requests as `localhost` for dev servers that reject unknown hosts (Vite, webpack, Django).
- **Quick Actions**: One-click URL copying, browser access, and QR code generation for mobile testing.
- **Runs in the tray**: switch tunnels on and off from the tray menu. When you quit with tunnels running, TunnelFlare asks whether to stop them.
- **Automatic updates**: TunnelFlare checks for new versions once a day, then downloads, verifies and installs them.

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

Download the file for your system from the [Releases](https://github.com/madroots/TunnelFlare/releases) page. Python, Qt and `cloudflared` are bundled, so there is nothing else to install.

| System | File | Requirements |
| --- | --- | --- |
| Linux x86_64 | `TunnelFlare-<version>-linux-x86_64.AppImage` | glibc 2.35+ (Ubuntu 22.04, Debian 12, Fedora 36 or newer) |
| macOS (Apple Silicon and Intel) | `TunnelFlare-<version>-macos-universal.dmg` | macOS 14+ |
| Windows x64 | `TunnelFlare-<version>-windows-x64-setup.exe` or `-portable.zip` | Windows 10 (1809)+ |

Builds are not code-signed yet:
- **macOS**: drag TunnelFlare to Applications. On first launch, go to **System Settings → Privacy & Security** and click **Open Anyway**.
- **Windows**: if SmartScreen appears, click **More info → Run anyway**. The installer does not need admin rights.
- **Linux**: [Gear Lever](https://github.com/mijorus/gearlever) is the recommended way to manage the AppImage. It adds TunnelFlare to your menu. Drag the AppImage into Gear Lever and click **Install/run**.

### Updates
TunnelFlare checks GitHub for a new version once a day. You can turn this off, or check right away, from the tray menu. **Update** downloads the new version, checks its SHA-256 checksum against the release's `SHA256SUMS.txt`, installs it and restarts TunnelFlare. Running tunnels stay online during the update.

Automatic installs work for the Windows installer version, the macOS app in Applications, and the Linux AppImage. The portable Windows zip opens the download page instead.

### Development Setup
Requirements: Python 3.11+, and the [cloudflared](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/) CLI on your `PATH` (packaged builds bundle their own).
```bash
git clone https://github.com/madroots/TunnelFlare
cd TunnelFlare
./setup.sh      # Windows: setup.bat
./run.sh        # Windows: run.bat
```
Dependencies are pinned with hashes in `requirements.txt` (app) and `requirements-dev.txt` (app plus test and build tools).

Run the tests and build a package for your platform:
```bash
python -m pip install --require-hashes -r requirements-dev.txt
python -m pytest
python packaging/build.py --target linux-x86_64   # or macos-universal, windows-x64
python packaging/smoke_test.py --target linux-x86_64
```
The release process, test strategy and signing roadmap are described in [docs/RELEASE_PLAN.md](docs/RELEASE_PLAN.md).

## Configuration
Application data and tunnel configurations are stored in `~/.tunnelflare`.
