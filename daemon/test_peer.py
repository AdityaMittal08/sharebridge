#!/usr/bin/env python3
# daemon/test_peer.py
import asyncio
import socket
import os
import signal
from typing import Dict, Any

from file_transfer import FileTransferManager
from screen_share import ScreenShareManager
from network_server import SignalingClient

# =====================================================================
# IMPORTANT: Change this to your Render WebSocket URL!
# =====================================================================
SIGNALING_SERVER_URL = ""

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

async def main():
    print("--- SHAREBRIDGE TEST PEER (WEBSOCKET MODE) ---")
    loop = asyncio.get_running_loop()
    
    # 1. File Server (Dynamic Port)
    dl_dir = os.path.expanduser("~/Downloads/ShareBridge_Test")
    tm = FileTransferManager(dl_dir, lambda t, p: print(f"[TestPeer] File: {p:.1f}%"))
    fs = await tm.start_server('0.0.0.0', 0)
    file_port = fs.sockets[0].getsockname()[1]
    
    # 2. WebRTC Server (Dynamic Port)
    sm = ScreenShareManager(lambda p: print(f"Incoming video from {p}!"))
    ws = await sm.start_signaling_server('0.0.0.0', 0)
    screen_port = ws.sockets[0].getsockname()[1]
    
    local_ip = get_local_ip()

    def on_peer_discovered(peer_data: Dict[str, Any]):
        print(f"[TestPeer] Discovered peer: {peer_data['id']} ({peer_data['name']}) at {peer_data['ip']}")

    def on_peer_lost(peer_id: str):
        print(f"[TestPeer] Peer lost: {peer_id}")

    # 3. WebSocket Matchmaker Setup
    print(f"[TestPeer] Connecting to Matchmaker at {SIGNALING_SERVER_URL}...")
    signaling_client = SignalingClient(
        server_url=SIGNALING_SERVER_URL,
        my_peer_id="device-test-peer-001",
        my_name="Test Laptop",
        local_ip=local_ip,
        file_port=file_port,
        screen_port=screen_port,
        on_add=on_peer_discovered,
        on_remove=on_peer_lost
    )
    
    signaling_client.start()

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
    print("[TestPeer] Disconnecting from signaling server...")
    signaling_client.stop()
    
    # Give asyncio a moment to flush the websocket closure
    await asyncio.sleep(0.5) 
    
    fs.close()
    ws.close()
    print("[TestPeer] Stopped cleanly.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass # Suppress any stray traceback prints