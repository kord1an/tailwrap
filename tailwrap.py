import subprocess
import json
import pystray
from PIL import Image, ImageDraw
import webbrowser
import pyperclip
import os
import threading
import time


# --- DATA FETCHING FUNCTIONS ---

def get_tailscale_data():
    """Fetches the main Tailscale status (devices, IPs, state) in JSON format."""
    try:
        result = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error fetching Tailscale status: {e}")
        return None

def get_tailscale_prefs():
    """Fetches Tailscale preferences (DNS, routes, etc.)."""
    try:
        result = subprocess.run(["tailscale", "debug", "prefs"], capture_output=True, text=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error fetching Tailscale prefs: {e}")
        return {}

def get_icon_image(is_connected):
    # This finds the absolute path to the directory where tailwrap.py is located
    current_dir = os.path.dirname(os.path.realpath(__file__))
    icon_name = "icon-active.png" if is_connected else "icon-inactive.png"
    filename = os.path.join(current_dir, "icons", icon_name)
    
    if os.path.exists(filename):
        return Image.open(filename)
    
    # Fallback if icon files are missing
    color = (0, 200, 0) if is_connected else (100, 100, 100)
    image = Image.new('RGB', (64, 64), color=color)
    d = ImageDraw.Draw(image)
    d.text((15, 25), "TS", fill=(255, 255, 255))
    return image

# --- CORE ACTIONS ---

def toggle_main_connection(icon, item):
    """Toggles the global Tailscale connection."""
    data = get_tailscale_data()
    if data and data.get("BackendState") == "Running":
        subprocess.run(["tailscale", "down"])
    else:
        subprocess.run(["tailscale", "up"])
    update_menu(icon)

def toggle_pref(flag_name, current_state, icon):
    """Toggles Tailscale flags like --accept-dns or --accept-routes."""
    new_state = "false" if current_state else "true"
    subprocess.run(["tailscale", "up", f"--{flag_name}={new_state}"])
    update_menu(icon)

def set_exit_node(ip, icon):
    """Sets or clears the Exit Node."""
    if ip is None:
        subprocess.run(["tailscale", "up", "--exit-node="])
    else:
        subprocess.run(["tailscale", "up", f"--exit-node={ip}"])
    update_menu(icon)

def copy_to_clipboard(text):
    """Copies the provided text to the system clipboard."""
    pyperclip.copy(text)

# --- ACTION HELPERS (Closures for pystray compatibility) ---

def make_copy_action(ip):
    """Returns a 2-argument function that copies a specific IP."""
    return lambda icon, item: copy_to_clipboard(ip)

def make_exit_node_action(ip):
    """Returns a 2-argument function that sets a specific Exit Node."""
    return lambda icon, item: set_exit_node(ip, icon)

def make_checked_state(is_active):
    """Returns a function that represents the checked state of an item."""
    return lambda item: is_active

# --- MENU BUILDERS ---

def build_network_menu(data):
    """Builds a submenu containing all peers in the Tailnet."""
    items = []
    peers = list(data.get("Peer", {}).values())
    
    # Sort: Online first, then alphabetically
    peers.sort(key=lambda p: (not p.get("Online", False), p.get("HostName", "").lower()))
    
    if not peers:
        return pystray.Menu(pystray.MenuItem("No other devices found", lambda: None, enabled=False))
        
    for peer in peers:
        hostname = peer.get("HostName", "Unknown")
        ip = peer.get("TailscaleIPs", ["No IP"])[0]
        is_online = peer.get("Online", False)
        os_name = peer.get("OS", "Unknown OS").capitalize()
        raw_tags = peer.get("Tags", [])
        
        status_icon = "🟢" if is_online else "🔴"
        clean_tags = [t.replace("tag:", "") for t in raw_tags]
        tags_str = f" [{', '.join(clean_tags)}]" if clean_tags else ""
        
        label = f"{status_icon} {hostname}{tags_str}"
        
        peer_menu = pystray.Menu(
            pystray.MenuItem(f"IP: {ip} (Click to copy)", make_copy_action(ip)),
            pystray.MenuItem(f"OS: {os_name}", lambda: None, enabled=False)
        )
        
        items.append(pystray.MenuItem(label, peer_menu))
        
    return pystray.Menu(*items)

def build_exit_nodes_menu(data, icon):
    """Builds a submenu for selecting an Exit Node."""
    items = []
    active_node_id = data.get("ExitNodeStatus", {}).get("ID")
    
    items.append(pystray.MenuItem(
        "None", 
        lambda: set_exit_node(None, icon),
        checked=lambda item: active_node_id is None,
        radio=True
    ))
    items.append(pystray.Menu.SEPARATOR)
    
    has_nodes = False
    for peer_id, peer in data.get("Peer", {}).items():
        if peer.get("ExitNodeOption"):
            has_nodes = True
            hostname = peer.get("HostName", "Unknown")
            ip = peer.get("TailscaleIPs", [""])[0]
            is_active = (peer_id == active_node_id)
            
            items.append(pystray.MenuItem(
                f"{hostname} ({ip})",
                make_exit_node_action(ip),
                checked=make_checked_state(is_active),
                radio=True
            ))
            
    if not has_nodes:
        items.append(pystray.MenuItem("No Exit Nodes available", lambda: None, enabled=False))
        
    return pystray.Menu(*items)

def build_preferences_menu(prefs, icon):
    """Builds a submenu for Tailscale preferences."""
    shields_up = prefs.get("ShieldsUp", False)
    use_dns = prefs.get("CorpDNS", True)
    use_subnets = prefs.get("RouteAll", True)

    return pystray.Menu(
        pystray.MenuItem(
            "Allow incoming connections",
            lambda: toggle_pref("shields-up", not shields_up, icon),
            checked=lambda item: not shields_up
        ),
        pystray.MenuItem(
            "Use Tailscale DNS settings",
            lambda: toggle_pref("accept-dns", use_dns, icon),
            checked=lambda item: use_dns
        ),
        pystray.MenuItem(
            "Use Tailscale subnets",
            lambda: toggle_pref("accept-routes", use_subnets, icon),
            checked=lambda item: use_subnets
        )
    )

def update_menu(icon, item=None):
    """Refresh data and rebuild the entire tray menu."""
    data = get_tailscale_data()
    prefs = get_tailscale_prefs()
    
    is_connected = data and data.get("BackendState") == "Running"
    icon.icon = get_icon_image(is_connected)
    
    menu_items = []
    
    # 1. Main Toggle
    status_text = "Connected" if is_connected else "Stopped"
    menu_items.append(pystray.MenuItem(
        f"Tailscale\n{status_text}", 
        toggle_main_connection, 
        checked=lambda item: is_connected
    ))
    menu_items.append(pystray.Menu.SEPARATOR)
    
    if is_connected:
        # 2. User Info
        user_id = data.get("Self", {}).get("UserID")
        user_profile = data.get("User", {}).get(str(user_id), {})
        user_name = user_profile.get("DisplayName", "User")
        user_email = user_profile.get("LoginName", "unknown@email.com")
        
        menu_items.append(pystray.MenuItem(f"👤 {user_name}", lambda: None, enabled=False))
        menu_items.append(pystray.MenuItem(f"✉️ {user_email}", lambda: None, enabled=False))
        menu_items.append(pystray.Menu.SEPARATOR)
        
        # 3. Local Device Info
        hostname = data.get("Self", {}).get("HostName", "Device")
        ip_address = data.get("TailscaleIPs", ["No IP"])[0]
        device_text = f"This device: {hostname} ({ip_address})"
        
        menu_items.append(pystray.MenuItem(device_text, make_copy_action(ip_address)))
        menu_items.append(pystray.Menu.SEPARATOR)
        
        # 4. Network and Exit Nodes
        menu_items.append(pystray.MenuItem("Network Devices", build_network_menu(data)))
        menu_items.append(pystray.MenuItem("Exit nodes", build_exit_nodes_menu(data, icon)))
        
    # 5. Settings and Exit
    menu_items.append(pystray.MenuItem("Preferences", build_preferences_menu(prefs, icon)))
    menu_items.append(pystray.Menu.SEPARATOR)
    menu_items.append(pystray.MenuItem("Admin Console...", lambda: webbrowser.open("https://login.tailscale.com/admin/machines")))
    menu_items.append(pystray.MenuItem("Exit", lambda: icon.stop()))
    
    icon.menu = pystray.Menu(*menu_items)

def background_update(icon):
    """Periodically refreshes the menu every 30 seconds."""
    while icon.visible:
        time.sleep(30)
        # Using icon.visible to stop the thread when the app closes
        if icon.visible:
            update_menu(icon)

def setup(icon):
    """Initial setup once the tray icon starts."""
    icon.visible = True
    update_menu(icon)

    # Start the background refresh thread
    thread = threading.Thread(target=background_update, args=(icon,), daemon=True)
    thread.start()


def main():
    """Main application entry point."""
    menu = pystray.Menu(pystray.MenuItem("Loading...", lambda: None))
    icon = pystray.Icon("Tailwrap", get_icon_image(False), "Tailwrap", menu)
    try:
        icon.run(setup=setup)
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    main()