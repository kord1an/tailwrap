#!/bin/bash

APP_NAME="tailwrap"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
CONFIG_DIR="$HOME/.config/$APP_NAME"

echo "🗑️  Uninstalling $APP_NAME..."

# 1. Close the running application
pkill -f "$APP_NAME" 2>/dev/null || true

# 2. Remove binary and desktop files
rm -f "$BIN_DIR/$APP_NAME"
rm -f "$DESKTOP_DIR/$APP_NAME.desktop"
rm -f "$AUTOSTART_DIR/$APP_NAME.desktop"

# 3. Remove code directory and venv
rm -rf "$INSTALL_DIR"

# 4. Remove config
read -p "Remove config file ($CONFIG_DIR/config.json)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$CONFIG_DIR"
    echo "🗑️  Config removed."
else
    echo "📁 Config kept at $CONFIG_DIR/config.json"
fi

echo "✅ $APP_NAME has been removed from your system."
