# daemon/dbus_interface.py
import json
import asyncio
from typing import Dict, Any, Optional
from dbus_next.service import ServiceInterface, method, signal
from file_transfer import FileTransferManager
from screen_share import ScreenShareManager
from zeroconf.asyncio import AsyncServiceBrowser

class ShareBridgeDaemonInterface(ServiceInterface):
    def __init__(self, name: str, my_peer_id: str):
        super().__init__(name)
        self.my_peer_id = my_peer_id
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.transfer_manager: Optional[FileTransferManager] = None
        self.screen_share: Optional[ScreenShareManager] = None
        self.zeroconf = None
        self.service_info = None
        self.is_paused = False
        self.stop_event: Optional[asyncio.Event] = None
        
        # New: Track the browser and listener
        self.browser: Optional[AsyncServiceBrowser] = None
        self.listener = None

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
    def SendFile(self, peer_id: 's', file_path: 's', transfer_id: 's') -> 'b': # type: ignore
        if peer_id not in self.peers or not self.transfer_manager: return False
        
        async def run_transfer():
            await self.transfer_manager.send_file(
                self.peers[peer_id]['ip'], 
                self.peers[peer_id]['port'], 
                file_path,
                transfer_id
            )

        asyncio.get_running_loop().create_task(run_transfer())
        return True

    @method()
    def StartScreenShare(self, peer_id: 's') -> 'b': # type: ignore
        if peer_id not in self.peers or not self.screen_share: return False
        target = self.peers[peer_id]
        asyncio.get_running_loop().create_task(
            self.screen_share.start_broadcasting(target['ip'], target.get('screen_port', 49155), self.my_peer_id)
        )
        return True

    @method()
    def StopScreenShare(self) -> 'b': # type: ignore
        if self.screen_share:
            self.screen_share.stop_stream()
        return True

    @method()
    def PauseDiscovery(self) -> 'b': # type: ignore
        if not self.is_paused and self.zeroconf and self.service_info:
            asyncio.get_running_loop().create_task(self.zeroconf.async_unregister_service(self.service_info))
            self.is_paused = True
            
            # Kill the scanner so it stops caching peers
            if self.browser:
                self.browser.cancel()
                self.browser = None

            for peer_id in list(self.peers.keys()):
                self.unregister_peer(peer_id)
        return True

    @method()
    def ResumeDiscovery(self) -> 'b': # type: ignore
        if self.is_paused and self.zeroconf and self.service_info:
            asyncio.get_running_loop().create_task(self.zeroconf.async_register_service(self.service_info))
            self.is_paused = False
            
            # Restart the scanner to force a fresh network query
            if self.listener:
                self.browser = AsyncServiceBrowser(self.zeroconf.zeroconf, "_sharebridge._tcp.local.", self.listener)
        return True

    @method()
    def Quit(self) -> 'b': # type: ignore
        if self.stop_event:
            self.stop_event.set()
        return True

    def register_peer(self, peer_data: Dict[str, Any]) -> None:
        if peer_data['id'] not in self.peers and not self.is_paused:
            self.peers[peer_data['id']] = peer_data
            self.PeerDiscovered(json.dumps(peer_data))

    def unregister_peer(self, peer_id: str) -> None:
        if peer_id in self.peers:
            del self.peers[peer_id]
            self.PeerLost(peer_id)