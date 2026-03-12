# daemon/network_server.py
"""
WebSocket Network Discovery for ShareBridge.
Replaces mDNS to bypass enterprise AP Isolation.
"""
import asyncio
import json
import websockets
from typing import Callable, Dict, Any

class SignalingClient:
    def __init__(self, server_url: str, my_peer_id: str, my_name: str, local_ip: str, file_port: int, screen_port: int, on_add: Callable[[Dict[str, Any]], None], on_remove: Callable[[str], None]):
        self.server_url = server_url
        self.my_peer_id = my_peer_id
        self.my_name = my_name
        self.local_ip = local_ip
        self.file_port = file_port
        self.screen_port = screen_port
        self.on_add = on_add
        self.on_remove = on_remove
        
        self.ws = None
        self.running = False
        self.task = None
        self.known_peers = set()

    def start(self):
        self.running = True
        self.task = asyncio.create_task(self._connect_loop())

    def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
        if self.ws:
            asyncio.create_task(self.ws.close())
        
        # Clear peers from the UI
        for old_id in list(self.known_peers):
            self.on_remove(old_id)
        self.known_peers.clear()

    async def _connect_loop(self):
        while self.running:
            try:
                async with websockets.connect(self.server_url) as ws:
                    self.ws = ws
                    print(f"[Signaling] Connected to matchmaker: {self.server_url}")
                    
                    # Register this device
                    reg_msg = {
                        "type": "register",
                        "peer_id": self.my_peer_id,
                        "name": self.my_name,
                        "local_ip": self.local_ip,
                        "file_port": self.file_port,
                        "screen_port": self.screen_port
                    }
                    await ws.send(json.dumps(reg_msg))

                    # Listen for peer updates
                    async for message in ws:
                        data = json.loads(message)
                        if data.get("type") == "peer_list":
                            self._update_peers(data.get("peers", []))
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Signaling] Disconnected: {e}. Retrying in 3s...")
                await asyncio.sleep(3)
                
    def _update_peers(self, active_peers_data):
        current_ids = set()
        for p in active_peers_data:
            if p["id"] == self.my_peer_id:
                continue # Don't add ourselves to the UI
            
            current_ids.add(p["id"])
            
            # If it's a new peer, trigger the D-Bus signal
            if p["id"] not in self.known_peers:
                peer_data = {
                    'id': p.get("id", "Unknown"),
                    'ip': p.get("ip", "0.0.0.0"),
                    'port': p.get("file_port", 0),
                    'screen_port': p.get("screen_port", 49155),
                    'name': p.get("name", "Unknown Peer") # <-- Safe extraction
                }
                self.on_add(peer_data)

        # Remove peers that went offline
        for old_id in list(self.known_peers):
            if old_id not in current_ids:
                self.on_remove(old_id)
                
        self.known_peers = current_ids