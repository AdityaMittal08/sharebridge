#!/usr/bin/env python3
# daemon/sharebridge-daemon.py
import asyncio
import socket
import uuid
import os
from typing import Dict, Any
from dbus_next.aio import MessageBus
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceInfo, AsyncServiceBrowser

from dbus_interface import ShareBridgeDaemonInterface
from network_server import PeerListener, SERVICE_TYPE
from file_transfer import FileTransferManager
from screen_share import ScreenShareManager

MY_PEER_ID = f"device-{uuid.getnode()}"
MY_NAME = os.getlogin().capitalize()
LISTEN_PORT = 49152

async def main() -> None:
    print("[Daemon] Starting ShareBridge Daemon...")
    loop = asyncio.get_running_loop()

    bus = await MessageBus().connect()
    dbus_interface = ShareBridgeDaemonInterface('org.gnome.shell.extensions.sharebridge.Daemon', MY_PEER_ID)
    bus.export('/org/gnome/shell/extensions/sharebridge/Daemon', dbus_interface)
    await bus.request_name('org.gnome.shell.extensions.sharebridge')

    download_dir = os.path.expanduser("~/Downloads/ShareBridge")
    transfer_manager = FileTransferManager(download_dir, lambda t_id, pct: dbus_interface.FileProgress(t_id, float(pct)))
    dbus_interface.transfer_manager = transfer_manager
    file_server = await transfer_manager.start_server('0.0.0.0', LISTEN_PORT)

    screen_share = ScreenShareManager(lambda p_id: dbus_interface.IncomingScreenShare(p_id))
    dbus_interface.screen_share = screen_share
    webrtc_server = await screen_share.start_signaling_server('0.0.0.0')

    aio_zc = AsyncZeroconf()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()

    # Inject into mDNS Broadcast
    service_info = AsyncServiceInfo(
        SERVICE_TYPE, f"{MY_PEER_ID}.{SERVICE_TYPE}",
        addresses=[socket.inet_aton(local_ip)], port=LISTEN_PORT,
        properties={
            'name': MY_NAME.encode('utf-8')
        }
    )
    
    await aio_zc.async_register_service(service_info)
    
    def on_peer_discovered(peer_data: Dict[str, Any]):
        dbus_interface.register_peer(peer_data)

    listener = PeerListener(loop, on_peer_discovered, dbus_interface.unregister_peer)
    browser = AsyncServiceBrowser(aio_zc.zeroconf, SERVICE_TYPE, listener)

    try:
        print("[Daemon] Running... (Press Ctrl+C to stop)")
        await asyncio.Future() 
    except asyncio.exceptions.CancelledError:
        pass
    finally:
        file_server.close()
        webrtc_server.close()
        await file_server.wait_closed()
        await webrtc_server.wait_closed()
        await aio_zc.async_unregister_service(service_info)
        await aio_zc.async_close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass