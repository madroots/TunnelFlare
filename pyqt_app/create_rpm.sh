#!/bin/bash

# Script to create an RPM package for CF Tunnel Manager (PyQt version) on openSUSE

set -e  # Exit on any error

echo "Creating RPM package for CF Tunnel Manager..."

# Create required directory structure
echo "Creating directory structure..."
mkdir -p BUILDROOT/usr/bin
mkdir -p BUILDROOT/usr/share/applications  
mkdir -p BUILDROOT/usr/share/icons/hicolor/256x256/apps
mkdir -p BUILDROOT/opt/cf-tunnel-manager

# Copy application files
echo "Copying application files..."
cp -r main.py requirements.txt setup.sh BUILDROOT/opt/cf-tunnel-manager/

# Create launcher script
cat > BUILDROOT/usr/bin/cf-tunnel-manager << 'EOF'
#!/bin/bash
cd /opt/cf-tunnel-manager
python3 main.py "$@"
EOF

chmod +x BUILDROOT/usr/bin/cf-tunnel-manager

# Create desktop entry
cat > BUILDROOT/usr/share/applications/cf-tunnel-manager.desktop << 'EOF'
[Desktop Entry]
Name=CF Tunnel Manager
Comment=A modern GUI for managing Cloudflare tunnels
Exec=/usr/bin/cf-tunnel-manager
Icon=cf-tunnel-manager
Terminal=false
Type=Application
Categories=Network;
StartupNotify=true
EOF

# Create a simple icon (we'll use a text file that can be converted to an image)
# For now, create a placeholder icon
convert -size 256x256 xc:blue -fill white -draw "rectangle 50,100 200,150" BUILDROOT/usr/share/icons/hicolor/256x256/apps/cf-tunnel-manager.png 2>/dev/null || echo "ImageMagick not available, creating text placeholder" && echo "Blue square icon" > BUILDROOT/usr/share/icons/hicolor/256x256/apps/cf-tunnel-manager.png

# Create the spec file
cat > cf-tunnel-manager.spec << 'EOF'
Name:           cf-tunnel-manager
Version:        1.0.0
Release:        1%{?dist}
Summary:        A modern GUI for managing Cloudflare tunnels

License:        MIT
BuildArch:      noarch

Requires:       python3 python3-PySide6 cloudflared

%description
CF Tunnel Manager is a modern GUI application for managing Cloudflare tunnels.
It provides a complete replacement for the shell script with a modern interface
featuring tunnel management, start/stop functionality, log viewing, and system tray support.

%files
/usr/bin/cf-tunnel-manager
/usr/share/applications/cf-tunnel-manager.desktop
/usr/share/icons/hicolor/256x256/apps/cf-tunnel-manager.png
/opt/cf-tunnel-manager/*

%pre
# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "cloudflared is not installed. Please install it with:"
    echo "  sudo dnf install cloudflared  # Fedora/RHEL"
    echo "  sudo zypper install cloudflared  # openSUSE"
    echo "  sudo apt install cloudflared  # Ubuntu/Debian"
    exit 1
fi

%post
# Create directories if they don't exist
mkdir -p ~/.cf-tunnels
mkdir -p ~/.cf-tunnels/logs

%changelog
* Fri Nov 21 2025 CF Tunnel Manager Team - 1.0.0-1
- Initial RPM package for CF Tunnel Manager
EOF

# Build the RPM
echo "Building RPM package..."
rpmbuild -bb --buildroot $PWD/BUILDROOT cf-tunnel-manager.spec

# Find the RPM and copy it to current directory
find $HOME/rpmbuild/RPMS -name "cf-tunnel-manager-*.rpm" -exec cp {} . \; 2>/dev/null || find /usr/src/packages/RPMS -name "cf-tunnel-manager-*.rpm" -exec cp {} . \; 2>/dev/null || echo "RPM not found in standard locations"

# Try to find the RPM in the build directory
if [ ! -f "cf-tunnel-manager-*.rpm" ]; then
    find . -name "cf-tunnel-manager-*.rpm" -exec cp {} . \; 2>/dev/null || echo "Could not find the built RPM"
fi

echo "RPM package creation completed!"
echo "Look for cf-tunnel-manager*.rpm in the current directory"
echo ""
echo "To install the package:"
echo "  sudo zypper install cf-tunnel-manager-*.rpm"
echo ""
echo "To run the application after installation:"
echo "  cf-tunnel-manager"