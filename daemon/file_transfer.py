# daemon/file_transfer.py
"""
Asynchronous TCP file transfer implementation with SHA-256 integrity checks.
Handles both the server (receiving) and client (sending) operations.
"""
import asyncio
import json
import os
import hashlib
import uuid
from typing import Callable

CHUNK_SIZE = 1024 * 1024  # 1 MB chunks for efficient memory usage

class FileTransferManager:
    def __init__(self, download_dir: str, progress_callback: Callable[[str, float], None]):
        self.download_dir = download_dir
        self.progress_callback = progress_callback
        os.makedirs(self.download_dir, exist_ok=True)

    async def start_server(self, host: str, port: int) -> asyncio.Server:
        """Starts the TCP server to listen for incoming files."""
        server = await asyncio.start_server(self._handle_client, host, port)
        return server

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handles an incoming file transfer asynchronously."""
        addr = writer.get_extra_info('peername')
        print(f"[FileTransfer] Incoming connection from {addr}")

        try:
            # 1. Read Header Size (4 bytes)
            header_size_bytes = await reader.readexactly(4)
            header_size = int.from_bytes(header_size_bytes, byteorder='big')

            # 2. Read Header JSON
            header_bytes = await reader.readexactly(header_size)
            header = json.loads(header_bytes.decode('utf-8'))
            
            filename = header['filename']
            total_size = header['filesize']
            transfer_id = header['transfer_id']
            
            # Prevent directory traversal attacks by securing the filename
            safe_filename = os.path.basename(filename)
            save_path = os.path.join(self.download_dir, safe_filename)
            
            # 3. Request User Consent via Native Dialog
            size_mb = total_size / (1024 * 1024)
            proc = await asyncio.create_subprocess_exec(
                'zenity', '--question',
                '--title=ShareBridge - Incoming File',
                f'--text=Do you want to accept "{safe_filename}" ({size_mb:.2f} MB)?',
                '--width=350'
            )
            await proc.wait()
            
            if proc.returncode != 0:
                print(f"[FileTransfer] Transfer of {safe_filename} rejected by user.")
                writer.write(b'REJECT')
                await writer.drain()
                return

            print(f"[FileTransfer] Receiving {safe_filename} ({total_size} bytes)")

            # 4. Read File Chunks and compute SHA-256 on the fly
            received_size = 0
            sha256_hash = hashlib.sha256()
            
            with open(save_path, 'wb') as f:
                while received_size < total_size:
                    chunk = await reader.read(min(CHUNK_SIZE, total_size - received_size))
                    if not chunk:
                        break
                    f.write(chunk)
                    sha256_hash.update(chunk)
                    received_size += len(chunk)
                    
                    # Report progress back to the GNOME UI
                    percent = (received_size / total_size) * 100
                    self.progress_callback(transfer_id, percent)

            # 5. Verify Integrity against the sender's hash
            calculated_hash = sha256_hash.hexdigest()
            if calculated_hash == header['sha256']:
                print(f"[FileTransfer] Success: {safe_filename} verified.")
                writer.write(b'OK')
            else:
                print(f"[FileTransfer] Hash mismatch for {safe_filename}!")
                writer.write(b'FAIL')
            await writer.drain()

        except asyncio.IncompleteReadError:
            print("[FileTransfer] Connection dropped before transfer completed.")
        except Exception as e:
            print(f"[FileTransfer] Error receiving file: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def send_file(self, target_ip: str, target_port: int, file_path: str, transfer_id: str = None) -> str:
        """Sends a file to a target peer over a raw TCP socket."""
        if not transfer_id:
            transfer_id = str(uuid.uuid4())
            
        if not os.path.exists(file_path):
            print(f"[FileTransfer] File not found: {file_path}")
            return transfer_id

        filesize = os.path.getsize(file_path)
        filename = os.path.basename(file_path)

        print(f"[FileTransfer] Calculating hash for {filename}...")
        
        # Offload hashing to a thread to prevent blocking the asyncio event loop
        def calc_hash():
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()

        loop = asyncio.get_running_loop()
        file_hash = await loop.run_in_executor(None, calc_hash)

        header = json.dumps({
            "filename": filename,
            "filesize": filesize,
            "sha256": file_hash,
            "transfer_id": transfer_id
        }).encode('utf-8')

        try:
            reader, writer = await asyncio.open_connection(target_ip, target_port)
            
            # 1. Send Header length and JSON payload
            writer.write(len(header).to_bytes(4, byteorder='big'))
            writer.write(header)
            await writer.drain()

            # 2. Stream File Chunks (The receiver will buffer until user accepts/rejects)
            sent_size = 0
            with open(file_path, 'rb') as f:
                while chunk := f.read(CHUNK_SIZE):
                    writer.write(chunk)
                    await writer.drain()
                    sent_size += len(chunk)
                    
                    # Report progress for our own UI
                    percent = (sent_size / filesize) * 100
                    self.progress_callback(transfer_id, percent)

            # 3. Wait for remote peer to verify the hash or reject
            status = await reader.read(1024)
            if status == b'OK':
                print(f"[FileTransfer] Transfer {transfer_id} completed and verified.")
            elif status == b'REJECT':
                print(f"[FileTransfer] Remote peer rejected the transfer.")
                self.progress_callback(transfer_id, 0) # Trigger failure reset
            else:
                print(f"[FileTransfer] Remote peer rejected the transfer (Hash mismatch).")

            writer.close()
            await writer.wait_closed()

        except ConnectionRefusedError:
            print(f"[FileTransfer] Connection refused by {target_ip}:{target_port}.")
        except Exception as e:
            print(f"[FileTransfer] Failed to send file: {e}")

        return transfer_id