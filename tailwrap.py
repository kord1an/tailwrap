__version__ = "1.1.0"

import subprocess
import json
import webbrowser
import pyperclip
import os
import time
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gio', '2.0')

try:
    gi.require_version('AyatanaAppIndicator', '0.1')
    from gi.repository import AyatanaAppIndicator as AppIndicator
except (ValueError, ImportError):
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as AppIndicator

try:
    gi.require_version('Notify', '0.7')
    from gi.repository import Notify
    Notify.init("tailwrap")
    _notify = True
except (ValueError, ImportError):
    _notify = False

from gi.repository import Gtk, GLib, Gio


# --- NOTIFICATIONS ---

def notify(title, body):
    if _notify:
        Notify.Notification.new(title, body, "dialog-information").show()
    else:
        print(f"[{title}] {body}")


# --- DATA FETCHING ---

def get_tailscale_data():
    try:
        result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error fetching Tailscale status: {e}")
        return None

def get_tailscale_prefs():
    try:
        result = subprocess.run(["tailscale", "debug", "prefs"], capture_output=True, text=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error fetching Tailscale prefs: {e}")
        return {}


# --- ICON ---

def get_icons_dir():
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "icons")

def set_indicator_icon(indicator, is_connected):
    icon_name = "icon-active" if is_connected else "icon-inactive"
    indicator.set_icon_theme_path(get_icons_dir())
    indicator.set_icon_full(icon_name, "Tailwrap")


# --- ASYNC SUBPROCESS HELPER ---

def run_tailscale(args, on_done, user_data=None):
    try:
        proc = Gio.Subprocess.new(args, Gio.SubprocessFlags.NONE)
    except GLib.GError as e:
        notify("Tailwrap Error", f"Failed to run: {e.message}")
        return
    proc.wait_check_async(None, on_done, user_data)


# --- CONFIG ---

CONFIG_DIR = os.path.expanduser("~/.config/tailwrap")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f)


# --- SUBNET ROUTER AUTO-DETECT ---

def detect_subnet_router(data):
    config = load_config()
    saved = config.get("subnet_router", {})

    for peer_id, peer in data.get("Peer", {}).items():
        hostname = peer.get("HostName", "")
        ip = peer.get("TailscaleIPs", [""])[0]
        tags = peer.get("Tags", [])
        routes = peer.get("Routes", [])

        # Match saved config first (hostname or IP)
        if saved and (hostname == saved.get("hostname") or ip == saved.get("ip")):
            return hostname, ip

        # Auto-detect: tagged as subnet-router or has advertised routes
        if "tag:subnet-router" in tags or routes:
            if peer.get("Online"):
                config["subnet_router"] = {"hostname": hostname, "ip": ip}
                save_config(config)
                return hostname, ip

    # Fall back to saved config even if peer is offline or not found
    if saved:
        return saved.get("hostname"), saved.get("ip")

    return None, None


# --- PING + PATH CACHE ---

_ping_cache = {"ts": 0, "path": None, "latency": None, "online": False}
PING_CACHE_TTL = 15

def refresh_ping_cache(ip):
    global _ping_cache
    now = time.time()
    if now - _ping_cache["ts"] < PING_CACHE_TTL:
        return

    try:
        result = subprocess.run(
            ["tailscale", "ping", "-c", "1", "--verbose", ip],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout + result.stderr

        if "pong" in output:
            _ping_cache["online"] = True
            idx = output.find("via DERP(")
            if idx != -1:
                start = idx + len("via DERP(")
                end = output.find(")", start)
                region = output[start:end] if end != -1 else "relay"
                _ping_cache["path"] = f"Relay: {region}"
            elif "via " in output:
                _ping_cache["path"] = "Direct"
            else:
                _ping_cache["path"] = "Unknown"

            ms_idx = output.find(" in ")
            if ms_idx != -1:
                rest = output[ms_idx + 4:]
                digits = ""
                for c in rest:
                    if c.isdigit():
                        digits += c
                    elif digits:
                        break
                _ping_cache["latency"] = int(digits) if digits else None
            else:
                _ping_cache["latency"] = None
        else:
            _ping_cache["online"] = False
            _ping_cache["path"] = None
            _ping_cache["latency"] = None
    except (subprocess.TimeoutExpired, Exception) as e:
        _ping_cache["online"] = False
        _ping_cache["path"] = None
        _ping_cache["latency"] = None

    _ping_cache["ts"] = time.time()


# --- HEALTH SECTION ---

def build_health_items(data, is_connected):
    items = []

    if not is_connected:
        return items

    subnet_hostname, subnet_ip = detect_subnet_router(data)

    if subnet_hostname and subnet_ip:
        refresh_ping_cache(subnet_ip)
        cache = _ping_cache

        if cache["online"]:
            path = cache.get("path", "Unknown")
            latency = cache.get("latency")
            latency_str = f" {latency}ms" if latency else ""
            item = Gtk.MenuItem(label=f"🟢 {subnet_hostname} ({path}{latency_str})")
        else:
            item = Gtk.MenuItem(label=f"🔴 {subnet_hostname} (Offline)")

        item.set_sensitive(False)
        items.append(item)
    else:
        item = Gtk.MenuItem(label="ℹ️ No subnet router detected")
        item.set_sensitive(False)
        items.append(item)

    return items


# --- CORE ACTIONS (async) ---

def toggle_main_connection(indicator):
    data = get_tailscale_data()
    if data and data.get("BackendState") == "Running":
        run_tailscale(["tailscale", "down"], on_toggle_done, indicator)
    else:
        run_tailscale(["tailscale", "up"], on_toggle_done, indicator)

def on_toggle_done(proc, task, indicator):
    try:
        proc.wait_check_finish(task)
        data = get_tailscale_data()
        if data and data.get("BackendState") == "Running":
            notify("Tailwrap", "Connected to Tailscale")
        else:
            notify("Tailwrap", "Disconnected from Tailscale")
    except GLib.GError as e:
        notify("Tailwrap Error", e.message.strip())
    GLib.idle_add(update_menu, indicator)

def toggle_pref(flag_name, desired, indicator):
    value = "true" if desired else "false"
    run_tailscale(
        ["tailscale", "set", f"--{flag_name}={value}"],
        lambda p, t, i: on_pref_done(p, t, i, flag_name),
        indicator
    )

def on_pref_done(proc, task, indicator, flag_name):
    try:
        proc.wait_check_finish(task)
    except GLib.GError as e:
        notify("Tailwrap Error", e.message.strip())
    GLib.idle_add(update_menu, indicator)

def set_exit_node(ip, indicator):
    if ip is None:
        args = ["tailscale", "set", "--exit-node="]
    else:
        args = ["tailscale", "set", f"--exit-node={ip}"]
    run_tailscale(args, lambda p, t, i: on_exit_node_done(p, t, i, ip), indicator)

def on_exit_node_done(proc, task, indicator, ip):
    try:
        proc.wait_check_finish(task)
    except GLib.GError as e:
        notify("Tailwrap Error", e.message.strip())
    GLib.idle_add(update_menu, indicator)

def copy_to_clipboard(text):
    pyperclip.copy(text)


# --- MENU BUILDERS ---

def build_network_menu(data):
    menu = Gtk.Menu()
    peers = list(data.get("Peer", {}).values())
    peers.sort(key=lambda p: (not p.get("Online", False), p.get("HostName", "").lower()))

    if not peers:
        item = Gtk.MenuItem(label="No other devices found")
        item.set_sensitive(False)
        menu.append(item)
        menu.show_all()
        return menu

    for peer in peers:
        hostname = peer.get("HostName", "Unknown")
        ip = peer.get("TailscaleIPs", ["No IP"])[0]
        is_online = peer.get("Online", False)
        os_name = peer.get("OS", "Unknown OS").capitalize()
        raw_tags = peer.get("Tags", [])
        clean_tags = [t.replace("tag:", "") for t in raw_tags]
        tags_str = f" [{', '.join(clean_tags)}]" if clean_tags else ""
        status_icon = "🟢" if is_online else "🔴"
        label = f"{status_icon} {hostname}{tags_str}"

        peer_menu = Gtk.Menu()
        copy_item = Gtk.MenuItem(label=f"IP: {ip}")
        copy_item.connect("activate", lambda *a, ip=ip: copy_to_clipboard(ip))
        peer_menu.append(copy_item)

        os_item = Gtk.MenuItem(label=f"OS: {os_name}")
        os_item.set_sensitive(False)
        peer_menu.append(os_item)
        peer_menu.show_all()

        parent = Gtk.MenuItem(label=label)
        parent.set_submenu(peer_menu)
        menu.append(parent)

    menu.show_all()
    return menu

def build_exit_nodes_menu(data, indicator):
    menu = Gtk.Menu()
    active_node_id = (data.get("ExitNodeStatus") or {}).get("ID")

    none_item = Gtk.RadioMenuItem.new_with_label(None, "None")
    if active_node_id is None:
        none_item.set_active(True)
    choices = [(none_item, None)]
    menu.append(none_item)

    radio_group = none_item
    menu.append(Gtk.SeparatorMenuItem.new())

    has_nodes = False
    for peer_id, peer in data.get("Peer", {}).items():
        if peer.get("ExitNodeOption"):
            has_nodes = True
            hostname = peer.get("HostName", "Unknown")
            ip = peer.get("TailscaleIPs", [""])[0]
            is_active = active_node_id is not None and peer.get("ID") == active_node_id
            item = Gtk.RadioMenuItem.new_with_label_from_widget(radio_group, f"{hostname} ({ip})")
            if is_active:
                item.set_active(True)
            choices.append((item, ip))
            menu.append(item)

    # Connect only after restoring selection; ignore the item being deselected.
    for item, ip in choices:
        item.connect("toggled", lambda selected, ip=ip:
                     set_exit_node(ip, indicator) if selected.get_active() else None)

    if not has_nodes:
        item = Gtk.MenuItem(label="No Exit Nodes available")
        item.set_sensitive(False)
        menu.append(item)

    menu.show_all()
    return menu

def build_preferences_menu(prefs, indicator):
    shields_up = prefs.get("ShieldsUp", False)
    use_dns = prefs.get("CorpDNS", True)
    use_subnets = prefs.get("RouteAll", True)

    menu = Gtk.Menu()

    item = Gtk.CheckMenuItem(label="Allow incoming connections")
    item.set_active(not shields_up)
    item.connect("activate", lambda *a: toggle_pref("shields-up", not shields_up, indicator))
    menu.append(item)

    item = Gtk.CheckMenuItem(label="Use Tailscale DNS settings")
    item.set_active(use_dns)
    item.connect("activate", lambda *a: toggle_pref("accept-dns", not use_dns, indicator))
    menu.append(item)

    item = Gtk.CheckMenuItem(label="Use Tailscale subnets")
    item.set_active(use_subnets)
    item.connect("activate", lambda *a: toggle_pref("accept-routes", not use_subnets, indicator))
    menu.append(item)

    menu.show_all()
    return menu


# --- MAIN MENU ---

def update_menu(indicator):
    data = get_tailscale_data()
    prefs = get_tailscale_prefs()

    is_connected = data and data.get("BackendState") == "Running"
    set_indicator_icon(indicator, is_connected)

    menu = Gtk.Menu()

    # 0. Connection Health
    health_items = build_health_items(data, is_connected)
    for item in health_items:
        menu.append(item)
    if health_items:
        menu.append(Gtk.SeparatorMenuItem.new())

    # 1. Main Toggle
    status_text = "Connected" if is_connected else "Stopped"
    main_item = Gtk.CheckMenuItem(label=f"Tailscale ({status_text})")
    main_item.set_active(is_connected)
    main_item.connect("activate", lambda *a: toggle_main_connection(indicator))
    menu.append(main_item)
    menu.append(Gtk.SeparatorMenuItem.new())

    if is_connected:
        # 2. User Info
        user_id = data.get("Self", {}).get("UserID")
        user_profile = data.get("User", {}).get(str(user_id), {})
        user_name = user_profile.get("DisplayName", "User")
        user_email = user_profile.get("LoginName", "unknown@email.com")

        name_item = Gtk.MenuItem(label=f"👤 {user_name}")
        name_item.set_sensitive(False)
        menu.append(name_item)

        email_item = Gtk.MenuItem(label=f"✉️ {user_email}")
        email_item.set_sensitive(False)
        menu.append(email_item)
        menu.append(Gtk.SeparatorMenuItem.new())

        # 3. Local Device Info
        hostname = data.get("Self", {}).get("HostName", "Device")
        ip_address = data.get("TailscaleIPs", ["No IP"])[0]
        device_item = Gtk.MenuItem(label=f"This device: {hostname} ({ip_address})")
        device_item.connect("activate", lambda *a, ip=ip_address: copy_to_clipboard(ip))
        menu.append(device_item)
        menu.append(Gtk.SeparatorMenuItem.new())

        # 4. Network and Exit Nodes
        net_item = Gtk.MenuItem(label="Network Devices")
        net_item.set_submenu(build_network_menu(data))
        menu.append(net_item)

        exit_item = Gtk.MenuItem(label="Exit nodes")
        exit_item.set_submenu(build_exit_nodes_menu(data, indicator))
        menu.append(exit_item)

    # 5. Preferences
    pref_item = Gtk.MenuItem(label="Preferences")
    pref_item.set_submenu(build_preferences_menu(prefs, indicator))
    menu.append(pref_item)
    menu.append(Gtk.SeparatorMenuItem.new())

    # 6. Admin Console
    admin_item = Gtk.MenuItem(label="Admin Console...")
    admin_item.connect("activate", lambda *a: webbrowser.open("https://login.tailscale.com/admin/machines"))
    menu.append(admin_item)
    menu.append(Gtk.SeparatorMenuItem.new())

    # 7. Exit
    exit_item = Gtk.MenuItem(label="Exit")
    exit_item.connect("activate", lambda *a: Gtk.main_quit())
    menu.append(exit_item)

    menu.show_all()
    indicator.set_menu(menu)


# --- TAILSCALE WATCH (realtime updates) ---

def try_start_watch(indicator, on_fallback):
    try:
        proc = subprocess.Popen(
            ["tailscale", "watch", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        fd = proc.stdout.fileno()
        channel = GLib.IOChannel.unix_new(fd)
        channel.set_encoding(None)
        GLib.io_add_watch(channel, GLib.IO_IN | GLib.IO_HUP, on_watch_event, indicator, proc)
        return proc
    except FileNotFoundError:
        on_fallback()
        return None

def on_watch_event(channel, condition, indicator, proc):
    if condition & GLib.IO_HUP:
        start_polling(indicator)
        return False

    while True:
        status, line, length, tpos = channel.read_line()
        if status != GLib.IOStatus.NORMAL:
            break
        if line and line.strip():
            try:
                json.loads(line.strip())
                GLib.idle_add(update_menu, indicator)
            except json.JSONDecodeError:
                pass

    return True


# --- POLLING FALLBACK ---

_polling_source_id = None

def start_polling(indicator):
    global _polling_source_id
    if _polling_source_id is None:
        _polling_source_id = GLib.timeout_add_seconds(30, lambda: poll_tick(indicator))

def poll_tick(indicator):
    update_menu(indicator)
    return True


# --- MAIN ---

def main():
    indicator = AppIndicator.Indicator.new(
        "tailwrap",
        "tailwrap",
        AppIndicator.IndicatorCategory.APPLICATION_STATUS
    )
    indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

    set_indicator_icon(indicator, False)

    update_menu(indicator)

    watch_proc = try_start_watch(indicator, lambda: start_polling(indicator))
    if watch_proc is None:
        start_polling(indicator)

    try:
        Gtk.main()
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    main()
