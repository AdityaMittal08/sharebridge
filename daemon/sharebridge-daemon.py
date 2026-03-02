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
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceInfo, AsyncServiceBrowser

gi.require_version('Gio', '2.0')
from gi.repository import Gio

# --- SCHEMA AUTO-DETECTION LOGIC ---
# This allows the script to find the compiled schema even if XDG_DATA_DIRS isn't set
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
schema_path = os.path.join(parent_dir, 'schemas')

if os.path.exists(os.path.join(schema_path, 'gschemas.compiled')):
    # Inject the local schema path into the Gio search path
    source = Gio.SettingsSchemaSource.new_from_directory(schema_path, Gio.SettingsSchemaSource.get_default(), False)
    SCHEMA_ID = 'org.gnome.shell.extensions.sharebridge'
    schema_obj = source.lookup(SCHEMA_ID, True)
    if not schema_obj:
        print(f"Error: Could not find schema {SCHEMA_ID} in {schema_path}")
        sys.exit(1)
    settings = Gio.Settings.new_full(schema_obj, None, None)
else:
    # Fallback to system default if running inside the actual GNOME environment
    try:
        settings = Gio.Settings.new('org.gnome.shell.extensions.sharebridge')
    except Exception:
        print("Error: Settings schema not found. Please run 'glib-compile-schemas schemas/'")
        sys.exit(1)

from dbus_interface import ShareBridgeDaemonInterface
from network_server import PeerListener, SERVICE_TYPE
from file_transfer import FileTransferManager
from screen_share import ScreenShareManager

MY_PEER_ID = f"device-{uuid.getnode()}"
MY_NAME = os.getlogin().capitalize()
LISTEN_PORT = 49152

def get_download_dir(settings_obj) -> str:
    path = settings_obj.get_string("download-dir")
    if not path:
        path = os.path.expanduser("~/Downloads/ShareBridge")
    os.makedirs(path, exist_ok=True)
    return path

async def main() -> None:
    print("[Daemon] Starting ShareBridge Daemon...")
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
    file_server = await transfer_manager.start_server('0.0.0.0', LISTEN_PORT)

    # Settings Listener
    settings.connect('changed::download-dir', lambda s, k: setattr(transfer_manager, 'download_dir', get_download_dir(s)))

    # Screen Share Setup
    screen_share = ScreenShareManager(lambda p_id: dbus_interface.IncomingScreenShare(p_id))
    dbus_interface.screen_share = screen_share
    webrtc_server = await screen_share.start_signaling_server('0.0.0.0')

    # mDNS Discovery
    aio_zc = AsyncZeroconf()
    # ... (rest of mDNS logic from previous versions) ...
    
    # Discovery Start
    def on_peer_discovered(peer_data: Dict[str, Any]):
        dbus_interface.register_peer(peer_data)

    listener = PeerListener(loop, on_peer_discovered, dbus_interface.unregister_peer)
    browser = AsyncServiceBrowser(aio_zc.zeroconf, SERVICE_TYPE, listener)

    try:
        await asyncio.Future() 
    finally:
        await aio_zc.async_close()

if __name__ == '__main__':
    asyncio.run(main())