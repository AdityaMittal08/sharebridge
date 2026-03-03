# daemon/network_server.py
"""
mDNS Network Discovery for ShareBridge.
Listens for peers and safely extracts their ports dynamically.
"""
import socket
import asyncio
from typing import Callable, Dict, Any
from zeroconf import Zeroconf
from zeroconf.asyncio import AsyncServiceInfo

SERVICE_TYPE = "_sharebridge._tcp.local."

class PeerListener:
    def __init__(self, loop: asyncio.AbstractEventLoop, on_add: Callable[[Dict[str, Any]], None], on_remove: Callable[[str], None]):
        self.loop = loop
        self.on_add = on_add
        self.on_remove = on_remove

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.loop.create_task(self._resolve_service(zc, type_, name))

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.loop.create_task(self._resolve_service(zc, type_, name))

    async def _resolve_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = AsyncServiceInfo(type_, name)
        await info.async_request(zc, 3000)
        
        if info and info.addresses:
            props = {k.decode('utf-8'): v.decode('utf-8') for k, v in info.properties.items() if v is not None}
            
            peer_data = {
                'id': name.replace(f'.{type_}', ''),
                'ip': socket.inet_ntoa(info.addresses[0]),
                'port': info.port, # Primary port (File Transfer)
                'screen_port': int(props.get('screen_port', 49155)), # Extracted WebRTC port
                'name': props.get('name', 'Unknown Device')
            }
            self.on_add(peer_data)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        peer_id = name.replace(f'.{type_}', '')
        self.on_remove(peer_id)