# daemon/network_server.py
"""
ZeroConf (mDNS) network discovery for ShareBridge.
Broadcasts this device's presence and listens for other ShareBridge peers.
"""
import socket
import asyncio
from typing import Callable, Dict, Any
from zeroconf import Zeroconf, ServiceListener
from zeroconf.asyncio import AsyncServiceInfo

SERVICE_TYPE = "_sharebridge._tcp.local."

class PeerListener(ServiceListener):
    def __init__(self, loop: asyncio.AbstractEventLoop, on_add: Callable, on_remove: Callable):
        self.loop = loop
        self.on_add = on_add
        self.on_remove = on_remove

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Triggered by ZeroConf when a peer disconnects."""
        peer_id = name.replace(f".{SERVICE_TYPE}", "")
        self.loop.call_soon_threadsafe(self.on_remove, peer_id)

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Triggered by ZeroConf when a new peer is found."""
        # Schedule the async network request without blocking the main thread
        asyncio.run_coroutine_threadsafe(self._async_add(zc, type_, name), self.loop)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    async def _async_add(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Asynchronously fetch the peer's IP and metadata."""
        info = AsyncServiceInfo(type_, name)
        await info.async_request(zc, 3000) # 3-second timeout
        
        if info and info.addresses:
            ip_address = socket.inet_ntoa(info.addresses[0])
            peer_id = name.replace(f".{SERVICE_TYPE}", "")
            
            properties = {k.decode('utf-8'): v.decode('utf-8') for k, v in info.properties.items()}
            
            peer_data = {
                "id": peer_id,
                "name": properties.get('name', 'Unknown User'),
                "ip": ip_address,
                "port": info.port
            }
            self.on_add(peer_data)