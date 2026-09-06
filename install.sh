#!/bin/bash
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Please run the installer with sudo: sudo ./install.sh"
  exit 1
fi

echo "[1/4] Compiling Infra Lock..."
if [ ! -f "dist/infralock" ]; then
    # We drop privileges to build so it doesn't mess up user permissions in the repo
    sudo -u $SUDO_USER bash ./build.sh
fi

echo "[2/4] Installing system binary..."
rm -f /usr/local/bin/infralock
cp dist/infralock /usr/local/bin/infralock
chmod 755 /usr/local/bin/infralock

echo "[3/4] Installing Desktop App Launcher..."
cp logo.png /usr/share/pixmaps/infralock.png
cat << 'APP' > /usr/share/applications/infralock.desktop
[Desktop Entry]
Name=Infra Lock
Comment=Zero-Knowledge Biometric Engine
Exec=/usr/local/bin/infralock gui
Icon=/usr/share/pixmaps/infralock.png
Terminal=false
Type=Application
Categories=Security;System;Settings;
APP
update-desktop-database

echo "[4/4] Installation Complete!"
echo "-> You can now search for 'Infra Lock' in your app menu."
echo "-> Or type 'infralock gui' in your terminal."
