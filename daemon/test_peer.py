#!/usr/bin/env python3
# daemon/test_peer.py
import asyncio
import socket
import os
from typing import Dict, Any
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceInfo, AsyncServiceBrowser

from file_transfer import FileTransferManager
from screen_share import ScreenShareManager
from network_server import PeerListener

SERVICE_TYPE = "_sharebridge._tcp.local."
LISTEN_PORT = 49153
SIGNALING_PORT = 49157

async def main():
    print("--- SHAREBRIDGE TEST PEER ---")
    loop = asyncio.get_running_loop()
    
    # 1. File Server
    # Set up a dedicated directory for test peer downloads
    dl_dir = os.path.expanduser("~/Downloads/ShareBridge_Test")
    tm = FileTransferManager(dl_dir, lambda t, p: print(f"[TestPeer] File: {p:.1f}%"))
    fs = await tm.start_server('0.0.0.0', LISTEN_PORT)
    
    # 2. WebRTC Server
    # Initialize screen sharing manager with a notification callback
    sm = ScreenShareManager(lambda p: print(f"Incoming video from {p}!"))
    ws = await sm.start_signaling_server('0.0.0.0', SIGNALING_PORT)
    
    # 3. mDNS Setup
    # Broadcast service presence without encryption keys
    aio_zc = AsyncZeroconf()
    service_info = AsyncServiceInfo(
        SERVICE_TYPE, f"device-test-peer-001.{SERVICE_TYPE}",
        addresses=[socket.inet_aton('127.0.0.1')], port=LISTEN_PORT,
        properties={'name': b'Test Laptop'}
    )
    
    await aio_zc.async_register_service(service_info)
    print("Broadcasting mDNS presence...")

    # Discover other peers on the network
    def on_peer_discovered(peer_data: Dict[str, Any]):
        peer_id = peer_data['id']
        print(f"[TestPeer] Discovered peer: {peer_id}")

    listener = PeerListener(loop, on_peer_discovered, lambda p: None)
    browser = AsyncServiceBrowser(aio_zc.zeroconf, SERVICE_TYPE, listener)

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        # Graceful shutdown of servers and mDNS registration
        fs.close()
        ws.close()
        await asyncio.gather(fs.wait_closed(), ws.wait_closed())
        await aio_zc.async_unregister_service(service_info)
        await aio_zc.async_close()

if __name__ == '__main__':
    asyncio.run(main())