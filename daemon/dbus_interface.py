# daemon/dbus_interface.py
"""
D-Bus Interface Definition for ShareBridge Daemon.
Handles the IPC communication between the Python backend and the GNOME JS frontend.
"""
import json
import asyncio
from typing import Dict, Any, Optional
from dbus_next.service import ServiceInterface, method, signal
from file_transfer import FileTransferManager

class ShareBridgeDaemonInterface(ServiceInterface):
    def __init__(self, name: str):
        super().__init__(name)
        # Store active peers in memory: { "peer_id": { ...peer_data... } }
        self.peers: Dict[str, Dict[str, Any]] = {}
        # Will be injected by the main script
        self.transfer_manager: Optional[FileTransferManager] = None

    @method()
    def GetPeers(self) -> 's': # type: ignore
        """Returns a JSON string of all currently discovered peers."""
        return json.dumps(list(self.peers.values()))

    @signal()
    def PeerDiscovered(self, peer_json: 's') -> 's': # type: ignore
        """Emits a signal to GNOME when a new local peer is found."""
        return peer_json

    @signal()
    def PeerLost(self, peer_id: 's') -> 's': # type: ignore
        """Emits a signal to GNOME when a peer drops off the network."""
        return peer_id

    @signal()
    def FileProgress(self, transfer_id: 's', percentage: 'd') -> 'sd': # type: ignore
        """Emits progress percentage to the GNOME UI. 'sd' = String, Double"""
        return [transfer_id, percentage]

    @method()
    def SendFile(self, peer_id: 's', file_path: 's') -> 's': # type: ignore
        """Called by GNOME UI to initiate a file send."""
        if peer_id not in self.peers:
            print(f"[DBus] Error: Peer {peer_id} not found in state.")
            return "ERROR: Peer not found"
            
        if not self.transfer_manager:
            return "ERROR: Transfer manager not initialized"

        target_ip = self.peers[peer_id]['ip']
        target_port = self.peers[peer_id]['port']
        
        # Fire-and-forget the async task so we don't block the D-Bus return thread
        loop = asyncio.get_running_loop()
        loop.create_task(
            self.transfer_manager.send_file(target_ip, target_port, file_path)
        )
        
        return "transfer_started"

    # Internal methods to be called by the ZeroConf network listener
    def register_peer(self, peer_data: Dict[str, Any]) -> None:
        """Saves peer to state and emits D-Bus signal."""
        peer_id = peer_data['id']
        if peer_id not in self.peers:
            self.peers[peer_id] = peer_data
            self.PeerDiscovered(json.dumps(peer_data))
            print(f"[Daemon] Emitted PeerDiscovered for {peer_data['name']}")

    def unregister_peer(self, peer_id: str) -> None:
        """Removes peer from state and emits D-Bus signal."""
        if peer_id in self.peers:
            del self.peers[peer_id]
            self.PeerLost(peer_id)
            print(f"[Daemon] Emitted PeerLost for {peer_id}")