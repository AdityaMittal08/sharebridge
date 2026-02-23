#!/usr/bin/env python3
# daemon/test_peer.py
import asyncio
import socket
import os
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceInfo
from file_transfer import FileTransferManager
from screen_share import ScreenShareManager

SERVICE_TYPE = "_sharebridge._tcp.local."
LISTEN_PORT = 49153
SIGNALING_PORT = 49157  # Offset port to avoid crashing the main daemon

async def main():
    print("--- SHAREBRIDGE TEST PEER ---")
    
    # 1. File Transfer Server
    dl_dir = os.path.expanduser("~/Downloads/ShareBridge_Test")
    tm = FileTransferManager(dl_dir, lambda t, p: print(f"[TestPeer] File: {p:.1f}%"))
    fs = await tm.start_server('0.0.0.0', LISTEN_PORT)
    print(f"✅ File Server listening on {LISTEN_PORT}")

    # 2. WebRTC Server
    sm = ScreenShareManager(lambda p: print(f"📺 Incoming video from {p}!"))
    ws = await sm.start_signaling_server('0.0.0.0', SIGNALING_PORT)
    print(f"✅ WebRTC Server listening on {SIGNALING_PORT}")

    # 3. mDNS Broadcast
    aio_zc = AsyncZeroconf()
    service_info = AsyncServiceInfo(
        SERVICE_TYPE, f"device-test-peer-001.{SERVICE_TYPE}",
        addresses=[socket.inet_aton('127.0.0.1')], port=LISTEN_PORT,
        properties={'name': b'Test Laptop (Simulator)'}
    )
    
    await aio_zc.async_register_service(service_info)
    print("📡 Broadcasting via mDNS...")

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        fs.close()
        ws.close()
        await fs.wait_closed()
        await ws.wait_closed()
        await aio_zc.async_unregister_service(service_info)
        await aio_zc.async_close()

if __name__ == '__main__':
    asyncio.run(main())