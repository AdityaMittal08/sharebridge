# daemon/dbus_interface.py
import json
import asyncio
from typing import Dict, Any, Optional
from dbus_next.service import ServiceInterface, method, signal
from file_transfer import FileTransferManager
from screen_share import ScreenShareManager

class ShareBridgeDaemonInterface(ServiceInterface):
    def __init__(self, name: str, my_peer_id: str):
        super().__init__(name)
        self.my_peer_id = my_peer_id
        self.peers: Dict[str, Dict[str, Any]] = {}
        
        self.transfer_manager: Optional[FileTransferManager] = None
        self.screen_share: Optional[ScreenShareManager] = None

    @method()
    def GetPeers(self) -> 's': # type: ignore
        return json.dumps(list(self.peers.values()))

    @signal()
    def PeerDiscovered(self, peer_json: 's') -> 's': # type: ignore
        return peer_json

    @signal()
    def PeerLost(self, peer_id: 's') -> 's': # type: ignore
        return peer_id

    @signal()
    def FileProgress(self, transfer_id: 's', percentage: 'd') -> 'sd': # type: ignore
        return [transfer_id, percentage]

    @signal()
    def IncomingScreenShare(self, peer_id: 's') -> 's': # type: ignore
        return peer_id

    @method()
    def SendFile(self, peer_id: 's', file_path: 's') -> 's': # type: ignore
        if peer_id not in self.peers or not self.transfer_manager: return "ERROR"
        asyncio.get_running_loop().create_task(
            self.transfer_manager.send_file(self.peers[peer_id]['ip'], self.peers[peer_id]['port'], file_path)
        )
        return "transfer_started"

    @method()
    def StartScreenShare(self, peer_id: 's') -> 'b': # type: ignore
        if peer_id not in self.peers or not self.screen_share: return False
        asyncio.get_running_loop().create_task(
            self.screen_share.start_broadcasting(self.peers[peer_id]['ip'], self.my_peer_id)
        )
        return True

    @method()
    def StopScreenShare(self) -> 'b': # type: ignore
        if self.screen_share:
            self.screen_share.stop_stream()
        return True

    def register_peer(self, peer_data: Dict[str, Any]) -> None:
        if peer_data['id'] not in self.peers:
            self.peers[peer_data['id']] = peer_data
            self.PeerDiscovered(json.dumps(peer_data))

    def unregister_peer(self, peer_id: str) -> None:
        if peer_id in self.peers:
            del self.peers[peer_id]
            self.PeerLost(peer_id)