#!/usr/bin/env python3
# daemon/sharebridge-daemon.py
"""
Main entry point for the ShareBridge background daemon.
Ties together D-Bus IPC, ZeroConf networking, and the TCP File Transfer server.
"""
import asyncio
import socket
import uuid
import os
from dbus_next.aio import MessageBus
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceInfo, AsyncServiceBrowser

from dbus_interface import ShareBridgeDaemonInterface
from network_server import PeerListener, SERVICE_TYPE
from file_transfer import FileTransferManager

MY_PEER_ID = f"device-{uuid.getnode()}"
MY_NAME = os.getlogin().capitalize()
LISTEN_PORT = 49152

async def main() -> None:
    print("[Daemon] Starting ShareBridge Daemon...")
    loop = asyncio.get_running_loop()

    # 1. Initialize D-Bus
    bus = await MessageBus().connect()
    dbus_interface = ShareBridgeDaemonInterface('org.gnome.shell.extensions.sharebridge.Daemon')
    bus.export('/org/gnome/shell/extensions/sharebridge/Daemon', dbus_interface)
    await bus.request_name('org.gnome.shell.extensions.sharebridge')
    print("[Daemon] Claimed D-Bus name: org.gnome.shell.extensions.sharebridge")

    # 2. Initialize File Transfer Server
    # By default, save files to ~/Downloads/ShareBridge
    download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "ShareBridge")
    
    # Pass a lambda to trigger the DBus FileProgress signal whenever a chunk is written/read
    transfer_manager = FileTransferManager(
        download_dir=download_dir,
        progress_callback=lambda t_id, pct: dbus_interface.FileProgress(t_id, float(pct))
    )
    dbus_interface.transfer_manager = transfer_manager

    server = await transfer_manager.start_server('0.0.0.0', LISTEN_PORT)
    print(f"[Daemon] File Transfer Server listening on 0.0.0.0:{LISTEN_PORT}")

    # 3. Initialize Async ZeroConf (mDNS)
    aio_zc = AsyncZeroconf()
    
    local_ip = socket.gethostbyname(socket.gethostname())
    if local_ip.startswith("127."):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()

    service_info = AsyncServiceInfo(
        SERVICE_TYPE,
        f"{MY_PEER_ID}.{SERVICE_TYPE}",
        addresses=[socket.inet_aton(local_ip)],
        port=LISTEN_PORT,
        properties={'name': MY_NAME.encode('utf-8')}
    )
    
    await aio_zc.async_register_service(service_info)
    print(f"[Daemon] Broadcasting mDNS service on {local_ip}:{LISTEN_PORT}")

    listener = PeerListener(
        loop=loop,
        on_add=dbus_interface.register_peer,
        on_remove=dbus_interface.unregister_peer
    )
    browser = AsyncServiceBrowser(aio_zc.zeroconf, SERVICE_TYPE, listener)

    # 4. Keep the async loop running forever
    try:
        print("[Daemon] Running... (Press Ctrl+C to stop)")
        await asyncio.Future() 
    except asyncio.exceptions.CancelledError:
        pass
    finally:
        print("\n[Daemon] Shutting down...")
        server.close()
        await server.wait_closed()
        await aio_zc.async_unregister_service(service_info)
        await aio_zc.async_close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass