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

Download the file for your system from the [Releases](https://github.com/madroots/TunnelFlare/releases) page. Python, Qt and `cloudflared` are bundled, so there is nothing else to install.

| System | File | Requirements |
| --- | --- | --- |
| Linux x86_64 | `TunnelFlare-<version>-linux-x86_64.AppImage` | glibc 2.35+ (Ubuntu 22.04, Debian 12, Fedora 36 or newer) |
| macOS Apple Silicon / Intel | `TunnelFlare-<version>-macos-arm64.dmg` / `-macos-x86_64.dmg` | macOS 14+ |
| Windows x64 | `TunnelFlare-<version>-windows-x64-setup.exe` or `-portable.zip` | Windows 10 (1809)+ |

Builds are not code-signed yet:
- **macOS**: drag TunnelFlare to Applications. On first launch, go to **System Settings → Privacy & Security** and click **Open Anyway**.
- **Windows**: if SmartScreen appears, click **More info → Run anyway**. The installer does not need admin rights.
- **Linux**: [Gear Lever](https://github.com/mijorus/gearlever) is the recommended way to manage the AppImage. It adds TunnelFlare to your menu and installs updates. Drag the AppImage into Gear Lever and click **Install/run**.

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
python packaging/build.py --target linux-x86_64   # or macos-arm64, macos-x86_64, windows-x64
python packaging/smoke_test.py --target linux-x86_64
```
The release process, test strategy and signing roadmap are described in [docs/RELEASE_PLAN.md](docs/RELEASE_PLAN.md).

## Configuration
Application data and tunnel configurations are stored in `~/.tunnelflare`.
