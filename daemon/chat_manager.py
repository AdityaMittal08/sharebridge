# daemon/chat_manager.py
import asyncio
import json
import base64
from database import DatabaseManager

CHAT_PORT = 49154

class ChatManager:
    def __init__(self, db: DatabaseManager, on_new_message, crypto_manager):
        self.db = db
        self.on_new_message = on_new_message
        self.crypto = crypto_manager

    async def start_server(self, host: str, port: int):
        server = await asyncio.start_server(self._handle_client, host, port)
        print(f"[Chat] Server listening on {host}:{port} (E2EE Enabled)")
        return server

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        try:
            data = await reader.read(8192)
            if data:
                # 1. Parse the outer unencrypted envelope
                envelope = json.loads(data.decode('utf-8'))
                sender_id = envelope.get('sender_id')
                b64_cipher = envelope.get('encrypted_data')

                if not sender_id or not b64_cipher:
                    print(f"[Chat] ❌ Invalid secure envelope from {addr}")
                    return

                # 2. Decrypt the inner payload using AES-256-GCM
                ciphertext = base64.b64decode(b64_cipher)
                try:
                    decrypted_bytes = self.crypto.decrypt_data(sender_id, ciphertext)
                except ValueError as e:
                    print(f"[Chat] ❌ Decryption failed for {sender_id}: {e}")
                    return

                payload = json.loads(decrypted_bytes.decode('utf-8'))
                message = payload.get('message', '')
                
                # 3. Save to database and trigger UI
                await self.db.save_message(sender_id, "incoming", message)
                self.on_new_message(sender_id, message)
                print(f"[Chat] 🔒 Received and decrypted message from {sender_id}")

        except Exception as e:
            print(f"[Chat] Error receiving secure message: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def send_message(self, target_ip: str, target_peer_id: str, my_peer_id: str, message: str) -> bool:
        # Localhost testing bypass to prevent port collision
        target_port = 49158 if target_ip == '127.0.0.1' else CHAT_PORT
        
        try:
            # 1. Create the inner payload and encrypt it
            inner_payload = json.dumps({'message': message}).encode('utf-8')
            ciphertext = self.crypto.encrypt_data(target_peer_id, inner_payload)
            
            # 2. Create the plain-text outer envelope
            envelope = json.dumps({
                'sender_id': my_peer_id,
                'encrypted_data': base64.b64encode(ciphertext).decode('utf-8')
            }).encode('utf-8')

            # 3. Send the secure envelope over the network
            reader, writer = await asyncio.open_connection(target_ip, target_port)
            writer.write(envelope)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

            # 4. Save to our own database
            await self.db.save_message(target_peer_id, "outgoing", message)
            print(f"[Chat] 🔒 Encrypted and sent message to {target_peer_id}")
            return True
        except ValueError as e:
            print(f"[Chat] ❌ Cannot send secure message: {e}")
            return False
        except Exception as e:
            print(f"[Chat] Error sending secure message: {e}")
            return False