#!/usr/bin/env python3
# daemon/test_peer.py
import asyncio
import socket
import os
import signal
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
    dl_dir = os.path.expanduser("~/Downloads/ShareBridge_Test")
    tm = FileTransferManager(dl_dir, lambda t, p: print(f"[TestPeer] File: {p:.1f}%"))
    fs = await tm.start_server('0.0.0.0', LISTEN_PORT)
    
    # 2. WebRTC Server
    sm = ScreenShareManager(lambda p: print(f"Incoming video from {p}!"))
    ws = await sm.start_signaling_server('0.0.0.0', SIGNALING_PORT)
    
    # 3. mDNS Setup
    aio_zc = AsyncZeroconf()
    service_info = AsyncServiceInfo(
        SERVICE_TYPE, f"device-test-peer-001.{SERVICE_TYPE}",
        addresses=[socket.inet_aton('127.0.0.1')], port=LISTEN_PORT,
        properties={
            'name': b'Test Laptop',
            'screen_port': str(SIGNALING_PORT).encode('utf-8')
        }
    )
    
    await aio_zc.async_register_service(service_info)
    print("Broadcasting mDNS presence... (Press Ctrl+C to stop)")

    def on_peer_discovered(peer_data: Dict[str, Any]):
        print(f"[TestPeer] Discovered peer: {peer_data['id']}")

    listener = PeerListener(loop, on_peer_discovered, lambda p: print(f"[TestPeer] Peer lost: {p}"))
    browser = AsyncServiceBrowser(aio_zc.zeroconf, SERVICE_TYPE, listener)

    # 4. Graceful Shutdown Handling
    stop_event = asyncio.Event()
    
    def shutdown_handler():
        print("\n[TestPeer] Shutdown signal received, initiating graceful exit...")
        stop_event.set()

    # Intercept Ctrl+C so it sets our event INSTEAD of violently crashing asyncio
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler)

    # Pause execution here until Ctrl+C is pressed
    await stop_event.wait()
    
    # --- CLEAN SHUTDOWN SEQUENCE ---
    print("[TestPeer] Sending mDNS Goodbye packet...")
    await aio_zc.async_unregister_service(service_info)
    
    # CRITICAL: Wait 500ms before closing zeroconf. 
    # This gives the OS network stack enough time to flush the UDP multicast packet!
    await asyncio.sleep(0.5) 
    
    await aio_zc.async_close()
    fs.close()
    ws.close()
    print("[TestPeer] Stopped cleanly.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass # Suppress any stray traceback prints