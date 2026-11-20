# TunnelFlare release plan: Linux, macOS, Windows

Goal: one app, identical on every desktop OS, that installs with nothing else
required, and whose release artifacts are tested on their own OS before they are
published.

## Platforms and artifacts

| Platform | Artifact | Minimum OS | Built on (GitHub runner) |
| --- | --- | --- | --- |
| Linux x86_64 | `TunnelFlare-<v>-linux-x86_64.AppImage` (+ `.zsync` for Gear Lever updates) | glibc 2.35: Ubuntu 22.04, Debian 12, Fedora 36, openSUSE Leap 16 or newer | `ubuntu-22.04` |
| macOS Apple Silicon | `TunnelFlare-<v>-macos-arm64.dmg` | macOS 14 Sonoma | `macos-15` |
| macOS Intel | `TunnelFlare-<v>-macos-x86_64.dmg` | macOS 14 Sonoma | `macos-15-intel` (GitHub retires it in August 2027) |
| Windows x64 | `TunnelFlare-<v>-windows-x64-setup.exe` (per-user, no admin) and `-portable.zip` | Windows 10 1809 / Windows 11 (ARM PCs run it through x64 emulation) | `windows-2025` |

Minimums come from the toolchain: PySide6 6.12 wheels need macOS 14 and glibc
2.34; Qt 6.12 supports Windows 10 1809+. cloudflared publishes no Windows ARM64
build, so Windows ships x64 only.

## Everything is bundled

Users install one file. Inside it:

- **Python 3.14** runtime (bugfix support until 2027-10, security fixes until 2030-10).
- **Qt 6.12 LTS** via `PySide6-Essentials` only (no Qt WebEngine or other unused modules).
- **cloudflared 2026.11.1**, pinned in `packaging/cloudflared.json` and verified
  against SHA-256 checksums before it is bundled. On first use the app copies it
  to `~/.tunnelflare/bin/` so firewall rules keep a stable path across updates;
  newer releases replace that copy atomically.
- Bundled **Inter** and **JetBrains Mono** fonts (SIL OFL) and third-party license notices.

Nothing is downloaded at runtime, so the app works the same offline, behind
proxies, and on locked-down machines.

## Identical app on every OS

- **Same code and dependency set**: one PyInstaller spec, one Python version, and
  hash-locked dependencies (`requirements.txt`, `requirements-dev.txt`, generated
  by `uv pip compile --universal --generate-hashes`, installed with
  `pip --require-hashes`).
- **Same look**: Qt's Fusion style, a fixed dark palette that ignores the OS
  light/dark setting, and bundled fonts at a fixed pixel size. The stylesheet names
  only bundled font families.
- **Same behaviour**: config in `~/.tunnelflare` everywhere. Closing the window
  hides the app to the tray (left-click restores it). Quit leaves running tunnels
  up, and they are rediscovered on the next launch. The cloudflared command line is
  identical except for transport flags kept from earlier Windows networking fixes
  (`--protocol http2 --edge-ip-version 4`, and `127.0.0.1` instead of `localhost`).
- **Proof**: CI uploads a screenshot of the main window from each OS's packaged
  app with every build, for side-by-side comparison.

## Packaging (implemented in `packaging/`)

- PyInstaller 6.22.3 in **onedir** mode on all OSes. No onefile: it starts
  faster, triggers fewer antivirus false positives, keeps Qt as replaceable
  shared libraries (LGPL-3.0 relinking), and onefile `.app` bundles are deprecated.
- Linux: AppDir + `appimagetool` 1.9.1 (pinned and checksum-verified), with
  update information embedded so Gear Lever can update from GitHub Releases.
- macOS: `.app` bundle (`io.github.madroots.tunnelflare`) in a drag-to-Applications DMG.
- Windows: Inno Setup installer (per-user install to
  `%LOCALAPPDATA%\Programs\TunnelFlare`, Start Menu shortcut, uninstaller,
  in-place upgrades that replace the old runtime), plus a portable zip.
- `python packaging/build.py --target <target>` builds one target. CI calls the same command.

## Testing

| Layer | What it proves | Where |
| --- | --- | --- |
| Static check | Syntax errors and undefined names (`ruff`) | Every push and PR |
| Unit and GUI tests (`pytest`, `pytest-qt`, offscreen) | Config writes are atomic. Tunnel start/stop/URL detection. A reused PID is never reported or killed. Exited tunnels are not shown as running. Startup errors reach the user and unlock the controls. Delete is locked while a start runs. QR rendering. Every stylesheet font weight maps to the bundled face. A fake cloudflared keeps these tests fast and offline. | Linux, macOS, Windows on Python 3.14, plus Linux on Python 3.11 |
| Packaged-app self-test (`TunnelFlare --self-test`) | The **final artifact** runs on its OS: resources, fonts, SVG plugins, QR code, bundled cloudflared version, main window render plus screenshot. Linux runs the AppImage under Xvfb. macOS mounts the DMG, verifies the code signature and runs the copied `.app`. Windows installs silently, runs, and uninstalls, and also tests the portable zip. | Every build of every target |
| End-to-end (`--self-test --e2e`) | The packaged app opens a **real Cloudflare quick tunnel** to a local web server and fetches the page back through the public `trycloudflare.com` URL, then stops the tunnel. Retried up to 3 times for network flakiness. | Every build of every target |
| Manual release check | First-run experience: Gatekeeper/SmartScreen prompts, firewall prompt, tray behaviour, scanning the QR code with a phone, upgrading over the previous version | Before announcing a release |

A release is published only if every job above passes for every target.

## Release pipeline (`.github/workflows/build.yml`)

1. **test** – lint plus the test matrix.
2. **package** – four targets in parallel: build, then self-test and E2E against
   the final artifact. Artifacts, self-test reports and screenshots are uploaded.
3. **release** – only for `v*` tags: checks that the tag equals the app version,
   collects the artifacts, writes `SHA256SUMS.txt`, and publishes the GitHub Release.

Cutting a release: bump `__version__` in `tunnelflare_backend/__init__.py`, commit,
then tag `v<version>` and push the tag. Third-party actions are pinned by commit SHA.

## Code signing (needs the owner's accounts)

Builds are currently **unsigned**: macOS apps are ad-hoc signed and Windows binaries are unsigned.

- macOS 15+: the first launch is blocked. Users open **System Settings → Privacy &
  Security → Open Anyway**, or run `xattr -dr com.apple.quarantine /Applications/TunnelFlare.app`.
- Windows: SmartScreen shows "Windows protected your PC". Users click **More info → Run anyway**.

To remove those prompts:

1. **macOS**: join the Apple Developer Program (USD 99/year). Create a Developer ID
   Application certificate and an App Store Connect API key, and store them as
   repository secrets. Then sign with hardened runtime (`MACOS_CODESIGN_IDENTITY`
   is already wired into the PyInstaller spec), notarize with
   `xcrun notarytool submit --wait`, and staple the DMG.
2. **Windows**: use either Azure Artifact Signing (about USD 9.99/month; individuals
   in the US/Canada, organizations in more countries) or SignPath Foundation (free
   for OSI-licensed open source; requires adding a license to the repository first).
   Sign `TunnelFlare.exe` and the installer. SmartScreen reputation still builds up
   over time; EV certificates no longer skip that.
3. Add a `LICENSE` file. The repository has none, which also blocks SignPath and
   leaves redistribution terms unclear.

## Keeping it safe and current

| Component | Policy | Next action |
| --- | --- | --- |
| Qt / PySide6 | Stay on the current LTS line (6.12). Open-source patch releases stop when Qt 6.13 ships. | Move to 6.13 around April 2027 |
| Python | Bundle the newest version in bugfix support | Re-evaluate 3.15 in 2027 |
| cloudflared | Bump the version and checksums in `packaging/cloudflared.json` with each release | Check monthly |
| Python packages | Regenerate the lock files: `uv pip compile` commands in their headers | Monthly, or when an advisory appears |
| GitHub Actions | Pinned SHAs; review updates quarterly | — |
| macOS Intel | `macos-15-intel` is GitHub's last Intel runner | Drop Intel or build universal2 before August 2027 |
