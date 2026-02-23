#!/usr/bin/env python3
# daemon/test_peer.py
import asyncio
import socket
import os
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceInfo
from file_transfer import FileTransferManager

SERVICE_TYPE = "_sharebridge._tcp.local."
LISTEN_PORT = 49153  # Port 49153 so it doesn't collide with the main daemon's 49152
MY_PEER_ID = "device-test-peer-001"
MY_NAME = "Test Laptop (Simulator)"

async def main():
    print("--- SHAREBRIDGE TEST PEER ---")
    
    # 1. Start the File Transfer Server
    # Save files to a separate folder so we can easily see the transfer worked
    download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "ShareBridge_Test")
    transfer_manager = FileTransferManager(
        download_dir=download_dir,
        progress_callback=lambda t_id, pct: print(f"[TestPeer] Receiving: {pct:.1f}%")
    )
    
    server = await transfer_manager.start_server('0.0.0.0', LISTEN_PORT)
    print(f"✅ Listening for incoming files on port {LISTEN_PORT}...")
    print(f"📂 Saving received files to: {download_dir}")

    # 2. Broadcast presence via mDNS
    aio_zc = AsyncZeroconf()
    local_ip = '127.0.0.1' # Loopback for local testing
    
    service_info = AsyncServiceInfo(
        SERVICE_TYPE,
        f"{MY_PEER_ID}.{SERVICE_TYPE}",
        addresses=[socket.inet_aton(local_ip)],
        port=LISTEN_PORT,
        properties={'name': MY_NAME.encode('utf-8')}
    )
    
    await aio_zc.async_register_service(service_info)
    print(f"📡 Broadcasting as '{MY_NAME}' via mDNS...")

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        print("\nShutting down test peer...")
    finally:
        server.close()
        await server.wait_closed()
        await aio_zc.async_unregister_service(service_info)
        await aio_zc.async_close()

if __name__ == '__main__':
    asyncio.run(main())