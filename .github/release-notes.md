## Downloads

| Platform | File |
| --- | --- |
| Linux x86_64 | `TunnelFlare-{{VERSION}}-linux-x86_64.AppImage` |
| macOS Apple Silicon (M1 and newer) | `TunnelFlare-{{VERSION}}-macos-arm64.dmg` |
| macOS Intel | `TunnelFlare-{{VERSION}}-macos-x86_64.dmg` |
| Windows x64 | `TunnelFlare-{{VERSION}}-windows-x64-setup.exe` (installer, no admin rights needed) or `TunnelFlare-{{VERSION}}-windows-x64-portable.zip` |

Everything is included: Python, Qt and cloudflared {{CLOUDFLARED_VERSION}} ship inside the app, so there is nothing else to install.
Requirements: macOS 14 or newer, Windows 10 (1809) or newer, Linux with glibc 2.35 or newer (Ubuntu 22.04, Debian 12, Fedora 36 and later).

### First launch

These builds are not code-signed yet, so the operating system asks once before opening them:

- **macOS**: open the DMG and drag TunnelFlare to Applications. On first launch macOS refuses to open it. Go to **System Settings → Privacy & Security** and click **Open Anyway**. Alternatively, run `xattr -dr com.apple.quarantine /Applications/TunnelFlare.app`.
- **Windows**: if SmartScreen shows "Windows protected your PC", click **More info → Run anyway**.
- **Linux**: run `chmod +x TunnelFlare-*.AppImage` and then start it, or install it with [Gear Lever](https://github.com/mijorus/gearlever), which also handles updates.

Each file has a checksum in `SHA256SUMS.txt`. Before publishing, every build passed the test suite on Linux, macOS and Windows and a packaged-app self-test on its own OS, including a live Cloudflare quick tunnel.
