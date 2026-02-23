# daemon/crypto_manager.py
import os
import base64
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

class CryptoManager:
    def __init__(self):
        self.private_key = x25519.X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.shared_keys = {}
        self.peer_public_keys = {}  # Tracks the raw keys to detect if a peer restarted

    def get_public_key_b64(self) -> str:
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return base64.b64encode(public_bytes).decode('utf-8')

    def derive_shared_key(self, peer_id: str, peer_public_b64: str) -> None:
        # If the peer restarted and broadcasted a NEW key, let it overwrite the old one!
        if peer_id in self.peer_public_keys and self.peer_public_keys[peer_id] == peer_public_b64:
            return

        try:
            peer_public_bytes = base64.b64decode(peer_public_b64)
            peer_pub_key = x25519.X25519PublicKey.from_public_bytes(peer_public_bytes)
            
            shared_secret = self.private_key.exchange(peer_pub_key)
            
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'sharebridge-e2ee'
            ).derive(shared_secret)
            
            self.shared_keys[peer_id] = AESGCM(derived_key)
            self.peer_public_keys[peer_id] = peer_public_b64
            print(f"[Crypto] 🔒 Secure E2EE channel established with {peer_id}")
        except Exception as e:
            print(f"[Crypto] ❌ Failed to establish secure channel: {e}")

    def encrypt_data(self, peer_id: str, plaintext: bytes) -> bytes:
        if peer_id not in self.shared_keys:
            raise ValueError(f"No secure channel established with {peer_id}")
        nonce = os.urandom(12)
        ciphertext = self.shared_keys[peer_id].encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt_data(self, peer_id: str, encrypted_data: bytes) -> bytes:
        if peer_id not in self.shared_keys:
            raise ValueError(f"No secure channel established with {peer_id}")
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        try:
            return self.shared_keys[peer_id].decrypt(nonce, ciphertext, None)
        except InvalidTag:
            # THE FIX: Catch the invisible error and give it a helpful description
            raise ValueError("Keys mismatched (Peer likely restarted with a new identity)")