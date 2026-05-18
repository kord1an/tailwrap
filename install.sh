#!/bin/bash

APP_NAME="tailwrap"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"

echo "🚀 Installing $APP_NAME..."

# 1. Creating directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$AUTOSTART_DIR"

# 2. Copying files
cp -r . "$INSTALL_DIR/"

# 3. Setting up virtual environment and installing dependencies
echo "📦 Configuring Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# 4. Creating startup script
cat <<EOF > "$BIN_DIR/$APP_NAME"
#!/bin/bash
"$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/tailwrap.py"
EOF
chmod +x "$BIN_DIR/$APP_NAME"

# 5. Creating .desktop file
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

# 6. Copying to autostart
cp "$DESKTOP_DIR/$APP_NAME.desktop" "$AUTOSTART_DIR/"

echo "✅ Installation completed!"
echo "💡 You can now launch '$APP_NAME' from the application menu or by typing '$APP_NAME' in the terminal."
echo "⚠️ Remember to install the GNOME extension: 'AppIndicator and KStatusNotifierItem Support'."
