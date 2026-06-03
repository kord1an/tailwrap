# Tailwrap

**Tailwrap** is a lightweight, Python-based system tray application for [Tailscale](https://tailscale.com) on Linux (optimized for Fedora and GNOME).

It provides a fast and intuitive way to manage your Tailscale connection without opening a browser or using the CLI — right from your system tray.

## Features

- **Quick Connect/Disconnect** — Toggle Tailscale with a single click.
- **Connection Health Dashboard** — At-a-glance view of your subnet router's status, connection path (Direct vs DERP relay), and ping latency.
- **Real-time Updates** — Menu refreshes instantly when your network changes (no polling).
- **Desktop Notifications** — See connect/disconnect events and errors as native GNOME notifications.
- **Async I/O** — All `tailscale` commands run in the background. The UI never freezes.
- **Network Devices** — List all devices in your Tailnet with online/offline status and tags.
- **IP Copying** — Click any device IP to copy it to your clipboard.
- **Exit Nodes** — Easily select and switch between Exit Nodes.
- **Preferences** — Manage DNS settings, subnets, and incoming connections.
- **Auto-detect Subnet Router** — Automatically finds your subnet router and shows its status.
- **Distinct Tray Icons** — Full-color icon when connected, dimmed greyscale when disconnected.

## Prerequisites

1. **Tailscale** — [installed](https://tailscale.com/download) and authenticated (`tailscale up`).
2. **GNOME Extension** — [AppIndicator and KStatusNotifierItem Support](https://extensions.gnome.org/extension/615/appindicator-support/) (required for tray icons on GNOME/Wayland).
3. **System Dependencies** (Fedora):

   ```bash
   # Fedora 39 and older:
   sudo dnf install python3-devel gcc gobject-introspection-devel cairo-gobject-devel libappindicator-gtk3

   # Fedora 40+:
   sudo dnf install python3-devel gcc gobject-introspection-devel cairo-gobject-devel libayatana-appindicator-gtk3
   ```

   For other distros, install the equivalent packages for Python 3, GTK 3, GObject Introspection, and an AppIndicator provider.

## Installation

```bash
git clone https://github.com/kord1an/tailwrap.git
cd tailwrap
chmod +x install.sh
./install.sh
```

The installer will:

1. Copy files to `~/.local/share/tailwrap/`
2. Create a Python virtual environment and install dependencies
3. Add `tailwrap` to your application menu
4. Enable autostart on login

Launch it from your application menu or by running `tailwrap` in a terminal.

## Configuration

### Tailscale operator (no sudo)

Allow Tailwrap to toggle Tailscale without password prompts:

```bash
sudo tailscale up --operator=$USER
```

### Subnet router auto-detect

Tailwrap automatically detects your subnet router (scans for peers tagged `tag:subnet-router` or with advertised routes). The detected router is saved to `~/.config/tailwrap/config.json` for fast loading on subsequent launches.

To change the detected router, simply delete or edit the config file:

```json
{"subnet_router": {"hostname": "my-router", "ip": "100.64.0.1"}}
```

## Usage

Right-click the tray icon to open the menu:

```
┌─────────────────────────────┐
│ 🟢 my-router (Direct 8ms)   │  ← connection health
├─────────────────────────────┤
│ ☑ Tailscale (Connected)     │  ← click to toggle
├─────────────────────────────┤
│ 👤 User Name                │
│ ✉️ user@email.com           │
├─────────────────────────────┤
│ This device: hostname (IP)  │  ← click to copy IP
├─────────────────────────────┤
│ Network Devices ›           │
│ Exit nodes ›                │
│ Preferences ›               │
├─────────────────────────────┤
│ Admin Console...            │
│ Exit                        │
└─────────────────────────────┘
```

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

This removes the app files, venv, autostart entry, desktop entry, and config.

## Upgrading

After pulling new changes, re-run the installer to update:

```bash
git pull
./install.sh
```

Your config at `~/.config/tailwrap/config.json` will not be affected.

## License

MIT
