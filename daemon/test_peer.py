#!/usr/bin/env python3
# daemon/test_peer.py
import asyncio
import socket
import os
from typing import Dict, Any
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceInfo, AsyncServiceBrowser

from file_transfer import FileTransferManager
from screen_share import ScreenShareManager
from chat_manager import ChatManager
from crypto_manager import CryptoManager
from network_server import PeerListener

SERVICE_TYPE = "_sharebridge._tcp.local."
LISTEN_PORT = 49153
SIGNALING_PORT = 49157
CHAT_PORT = 49158  # Offset for localhost testing

class DummyDB:
    """Fake database for the test peer so it doesn't crash trying to save chats."""
    async def save_message(self, *args): pass

async def main():
    print("--- SHAREBRIDGE TEST PEER ---")
    loop = asyncio.get_running_loop()
    crypto = CryptoManager()
    print(f"🔑 Test Peer Public Key: {crypto.get_public_key_b64()[:15]}...")
    
    # 1. File Server
    dl_dir = os.path.expanduser("~/Downloads/ShareBridge_Test")
    tm = FileTransferManager(dl_dir, lambda t, p: print(f"[TestPeer] File: {p:.1f}%"))
    fs = await tm.start_server('0.0.0.0', LISTEN_PORT)
    
    # 2. WebRTC Server
    sm = ScreenShareManager(lambda p: print(f"📺 Incoming video from {p}!"))
    ws = await sm.start_signaling_server('0.0.0.0', SIGNALING_PORT)
    
    # 3. Secure Chat Server
    cm = ChatManager(DummyDB(), lambda p, m: print(f"\n💬 DECRYPTED MESSAGE FROM {p}:\n>>> {m}\n"), crypto)
    cs = await cm.start_server('0.0.0.0', CHAT_PORT)

    # 4. mDNS Setup
    aio_zc = AsyncZeroconf()
    service_info = AsyncServiceInfo(
        SERVICE_TYPE, f"device-test-peer-001.{SERVICE_TYPE}",
        addresses=[socket.inet_aton('127.0.0.1')], port=LISTEN_PORT,
        properties={'name': b'Test Laptop', 'pub_key': crypto.get_public_key_b64().encode('utf-8')}
    )
    
    await aio_zc.async_register_service(service_info)
    print("📡 Broadcasting mDNS with E2EE Key...")

    # THE FIX: Tell the test peer to listen for the main daemon's public key!
    def on_peer_discovered(peer_data: Dict[str, Any]):
        peer_id = peer_data['id']
        pub_key_b64 = peer_data.get('pub_key')
        if pub_key_b64:
            crypto.derive_shared_key(peer_id, pub_key_b64)
            print(f"[TestPeer] 🔒 Secured channel with {peer_id}")

    listener = PeerListener(loop, on_peer_discovered, lambda p: None)
    browser = AsyncServiceBrowser(aio_zc.zeroconf, SERVICE_TYPE, listener)

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        fs.close(); ws.close(); cs.close()
        await asyncio.gather(fs.wait_closed(), ws.wait_closed(), cs.wait_closed())
        await aio_zc.async_unregister_service(service_info)
        await aio_zc.async_close()

if __name__ == '__main__':
    asyncio.run(main())