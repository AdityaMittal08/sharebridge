#!/usr/bin/env python3
# daemon/sharebridge-daemon.py
import asyncio
import socket
import uuid
import os
import sys
import gi
from typing import Dict, Any
from dbus_next.aio import MessageBus

gi.require_version('Gio', '2.0')
from gi.repository import Gio

# --- SCHEMA AUTO-DETECTION LOGIC ---
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
schema_path = os.path.join(parent_dir, 'schemas')

if os.path.exists(os.path.join(schema_path, 'gschemas.compiled')):
    source = Gio.SettingsSchemaSource.new_from_directory(schema_path, Gio.SettingsSchemaSource.get_default(), False)
    SCHEMA_ID = 'org.gnome.shell.extensions.sharebridge'
    schema_obj = source.lookup(SCHEMA_ID, True)
    if not schema_obj:
        print(f"Error: Could not find schema {SCHEMA_ID} in {schema_path}")
        sys.exit(1)
    settings = Gio.Settings.new_full(schema_obj, None, None)
else:
    try:
        settings = Gio.Settings.new('org.gnome.shell.extensions.sharebridge')
    except Exception:
        print("Error: Settings schema not found. Please run 'glib-compile-schemas schemas/'")
        sys.exit(1)

from dbus_interface import ShareBridgeDaemonInterface
from network_server import SignalingClient
from file_transfer import FileTransferManager
from screen_share import ScreenShareManager

MY_PEER_ID = f"device-{uuid.getnode()}"
MY_NAME = os.getlogin().capitalize()

# =====================================================================
# IMPORTANT: Change this to the IP address of the laptop running server.py!
# If deployed on the web, it will look like "wss://your-app.onrender.com"
# =====================================================================
SIGNALING_SERVER_URL = ""

def get_download_dir(settings_obj) -> str:
    path = settings_obj.get_string("download-dir")
    if not path:
        path = os.path.expanduser("~/Downloads/ShareBridge")
    os.makedirs(path, exist_ok=True)
    return path

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

async def main() -> None:
    print("[Daemon] Starting ShareBridge Daemon (WebSocket Mode)...")
    loop = asyncio.get_running_loop()

    # D-Bus Setup
    bus = await MessageBus().connect()
    dbus_interface = ShareBridgeDaemonInterface('org.gnome.shell.extensions.sharebridge.Daemon', MY_PEER_ID)
    bus.export('/org/gnome/shell/extensions/sharebridge/Daemon', dbus_interface)
    await bus.request_name('org.gnome.shell.extensions.sharebridge')

    # File Transfer Setup
    current_download_dir = get_download_dir(settings)
    transfer_manager = FileTransferManager(current_download_dir, lambda t_id, pct: dbus_interface.FileProgress(t_id, float(pct)))
    dbus_interface.transfer_manager = transfer_manager
    file_server = await transfer_manager.start_server('0.0.0.0', 0)
    file_port = file_server.sockets[0].getsockname()[1]

    settings.connect('changed::download-dir', lambda s, k: setattr(transfer_manager, 'download_dir', get_download_dir(s)))

    # Screen Share Setup
    screen_share = ScreenShareManager(lambda p_id: dbus_interface.IncomingScreenShare(p_id))
    dbus_interface.screen_share = screen_share
    webrtc_server = await screen_share.start_signaling_server('0.0.0.0', 0)
    screen_port = webrtc_server.sockets[0].getsockname()[1]

    local_ip = get_local_ip()

    def on_peer_discovered(peer_data: Dict[str, Any]):
        dbus_interface.register_peer(peer_data)

    # Initialize and start the WebSocket Signaling Client
    signaling_client = SignalingClient(
        server_url=SIGNALING_SERVER_URL,
        my_peer_id=MY_PEER_ID,
        my_name=MY_NAME,
        local_ip=local_ip,
        file_port=file_port,
        screen_port=screen_port,
        on_add=on_peer_discovered,
        on_remove=dbus_interface.unregister_peer
    )
    
    dbus_interface.signaling_client = signaling_client
    signaling_client.start()

    # Graceful shutdown event
    stop_event = asyncio.Event()
    dbus_interface.stop_event = stop_event

    try:
        await stop_event.wait() 
    finally:
        print("[Daemon] Shutting down cleanly...")
        signaling_client.stop()

if __name__ == '__main__':
    asyncio.run(main())