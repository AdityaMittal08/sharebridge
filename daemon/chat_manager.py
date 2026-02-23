# daemon/chat_manager.py
"""
Asynchronous TCP server specifically for routing chat messages.
"""
import asyncio
import json
from typing import Callable
from database import DatabaseManager

CHAT_PORT = 49154

class ChatManager:
    def __init__(self, db: DatabaseManager, on_new_message: Callable[[str, str], None]):
        self.db = db
        self.on_new_message = on_new_message

    async def start_server(self, host: str, port: int) -> asyncio.Server:
        """Starts the lightweight TCP server for chat packets."""
        return await asyncio.start_server(self._handle_client, host, port)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handles an incoming chat packet."""
        try:
            data = await reader.read(4096)
            if data:
                payload = json.loads(data.decode('utf-8'))
                sender_id = payload['peer_id']
                message = payload['message']
                
                # 1. Save to SQLite
                await self.db.save_message(sender_id, False, message)
                
                # 2. Push to GNOME UI via D-Bus
                self.on_new_message(sender_id, message)
                print(f"[Chat] Received message from {sender_id}: {message[:20]}...")
                
        except Exception as e:
            print(f"[Chat] Error receiving message: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def send_message(self, target_ip: str, target_id: str, my_id: str, message: str) -> bool:
        """Fires a chat message to a peer over TCP."""
        try:
            reader, writer = await asyncio.open_connection(target_ip, CHAT_PORT)
            payload = json.dumps({"peer_id": my_id, "message": message}).encode('utf-8')
            
            writer.write(payload)
            await writer.drain()
            
            writer.close()
            await writer.wait_closed()
            
            # Save our own outgoing message to the database
            await self.db.save_message(target_id, True, message)
            return True
            
        except ConnectionRefusedError:
            print(f"[Chat] Peer {target_ip} is not accepting chat connections.")
            return False
        except Exception as e:
            print(f"[Chat] Failed to send message: {e}")
            return False