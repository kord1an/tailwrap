#!/bin/bash
set -e

APP_NAME="tailwrap"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"

echo "🚀 Installing $APP_NAME..."

# 1. Backup existing config if reinstalling
if [ -d "$INSTALL_DIR" ]; then
    if [ -f "$HOME/.config/$APP_NAME/config.json" ]; then
        cp "$HOME/.config/$APP_NAME/config.json" /tmp/tailwrap-config-backup.json
        echo "📦 Backed up config to /tmp/tailwrap-config-backup.json"
    fi
    echo "♻️  Removing previous installation..."
    rm -rf "$INSTALL_DIR"
fi

# 2. Creating directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$AUTOSTART_DIR"

# 3. Copying files (exclude venv and pycache)
rsync -a --exclude='venv/' --exclude='__pycache__/' --exclude='*.pyc' \
    --exclude='.git/' --exclude='.gitignore' \
    "$(dirname "$0")/" "$INSTALL_DIR/" || {
    cp -r "$(dirname "$0")"/*.py "$(dirname "$0")"/icons "$(dirname "$0")"/requirements.txt "$(dirname "$0")"/screenshot_tray.png "$INSTALL_DIR/"
}

# 4. Setting up virtual environment and installing dependencies
echo "📦 Configuring Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# 5. Creating startup script
cat <<EOF > "$BIN_DIR/$APP_NAME"
#!/bin/bash
"$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/tailwrap.py"
EOF
chmod +x "$BIN_DIR/$APP_NAME"

# 6. Creating .desktop file
cat <<EOF > "$DESKTOP_DIR/$APP_NAME.desktop"
[Desktop Entry]
Name=Tailwrap
Comment=Tailscale Tray Wrapper for Linux
Exec=$BIN_DIR/$APP_NAME
Icon=$INSTALL_DIR/icons/icon-active.png
Type=Application
Terminal=false
Categories=Network;Utility;
EOF

# 7. Copying to autostart
cp "$DESKTOP_DIR/$APP_NAME.desktop" "$AUTOSTART_DIR/"

# 8. Restore config if reinstalling
if [ -f /tmp/tailwrap-config-backup.json ]; then
    mkdir -p "$HOME/.config/$APP_NAME"
    cp /tmp/tailwrap-config-backup.json "$HOME/.config/$APP_NAME/config.json"
    rm /tmp/tailwrap-config-backup.json
    echo "♻️  Restored previous config"
fi

echo "✅ Installation completed!"
echo "💡 Launch: application menu → Tailwrap, or run 'tailwrap' in terminal."
echo "⚠️  Make sure the GNOME extension 'AppIndicator and KStatusNotifierItem Support' is installed."
echo "⚙️  Run: sudo tailscale up --operator=\$USER  (to avoid sudo prompts)"
