# daemon/screen_share.py
"""
WebRTC Video Sharing Manager via GStreamer.
Includes the native XDG Desktop Portal D-Bus client to securely capture Wayland screens
using isolated PipeWire File Descriptors.
"""
import asyncio
import json
import gi
import random
import threading
from typing import Callable, Optional

from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from dbus_next import Variant
from dbus_next.introspection import Node

gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp, GLib

SIGNALING_PORT = 49155

class WaylandScreenCapture:
    """Handles the heavy 4-step D-Bus handshake with GNOME's Wayland security portal."""
    
    PORTAL_XML = """
    <node>
        <interface name="org.freedesktop.portal.ScreenCast">
            <method name="CreateSession">
                <arg type="a{sv}" name="options" direction="in"/>
                <arg type="o" name="handle" direction="out"/>
            </method>
            <method name="SelectSources">
                <arg type="o" name="session_handle" direction="in"/>
                <arg type="a{sv}" name="options" direction="in"/>
                <arg type="o" name="handle" direction="out"/>
            </method>
            <method name="Start">
                <arg type="o" name="session_handle" direction="in"/>
                <arg type="s" name="parent_window" direction="in"/>
                <arg type="a{sv}" name="options" direction="in"/>
                <arg type="o" name="handle" direction="out"/>
            </method>
            <method name="OpenPipeWireRemote">
                <arg type="o" name="session_handle" direction="in"/>
                <arg type="a{sv}" name="options" direction="in"/>
                <arg type="h" name="fd" direction="out"/>
            </method>
        </interface>
    </node>
    """

    async def get_pipewire_node_id_and_fd(self) -> tuple:
        # THE FIX: We must negotiate_unix_fd=True to receive the secure video file descriptor
        bus = await MessageBus(bus_type=BusType.SESSION, negotiate_unix_fd=True).connect()
        
        intr = Node.parse(self.PORTAL_XML)
        obj = bus.get_proxy_object('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop', intr)
        screencast = obj.get_interface('org.freedesktop.portal.ScreenCast')
        
        sender_name = bus.unique_name[1:].replace('.', '_')
        
        # STEP 1: Create Session
        token1 = f"sharebridge_{random.randint(1000, 9999)}"
        req_path1 = f"/org/freedesktop/portal/desktop/request/{sender_name}/{token1}"
        future1 = asyncio.get_running_loop().create_future()
        
        def handler1(msg):
            if msg.path == req_path1 and msg.member == 'Response':
                if not future1.done(): future1.set_result((msg.body[0], msg.body[1]))
        bus.add_message_handler(handler1)
        
        await screencast.call_create_session({
            'session_handle_token': Variant('s', token1),
            'handle_token': Variant('s', token1)
        })
        res_code, results = await future1
        bus.remove_message_handler(handler1)
        if res_code != 0: raise Exception("Failed to create Wayland portal session")
        session_handle = results['session_handle'].value
        
        # STEP 2: Select Sources
        token2 = f"sharebridge_{random.randint(1000, 9999)}"
        req_path2 = f"/org/freedesktop/portal/desktop/request/{sender_name}/{token2}"
        future2 = asyncio.get_running_loop().create_future()
        
        def handler2(msg):
            if msg.path == req_path2 and msg.member == 'Response':
                if not future2.done(): future2.set_result((msg.body[0], msg.body[1]))
        bus.add_message_handler(handler2)
        
        await screencast.call_select_sources(session_handle, {
            'handle_token': Variant('s', token2),
            'types': Variant('u', 3),       
            'multiple': Variant('b', False)
        })
        res_code, _ = await future2
        bus.remove_message_handler(handler2)
        if res_code != 0: raise Exception("Failed to select Wayland sources")
            
        # STEP 3: Start Stream & Extract Node ID
        token3 = f"sharebridge_{random.randint(1000, 9999)}"
        req_path3 = f"/org/freedesktop/portal/desktop/request/{sender_name}/{token3}"
        future3 = asyncio.get_running_loop().create_future()
        
        def handler3(msg):
            if msg.path == req_path3 and msg.member == 'Response':
                if not future3.done(): future3.set_result((msg.body[0], msg.body[1]))
        bus.add_message_handler(handler3)
        
        await screencast.call_start(session_handle, '', {
            'handle_token': Variant('s', token3)
        })
        res_code, results = await future3
        bus.remove_message_handler(handler3)
        if res_code != 0: raise Exception("User cancelled the screen share prompt")
            
        streams = results['streams'].value
        node_id = streams[0][0]  
        
        # STEP 4: Extract the Isolated PipeWire File Descriptor
        fd = await screencast.call_open_pipe_wire_remote(session_handle, {})
        
        # Unpack the UNIX FD if wrapped by dbus_next
        if hasattr(fd, 'take'):
            fd = fd.take()

        print(f"[Portal] Successfully negotiated PipeWire Node ID: {node_id} on FD: {fd}")
        return node_id, fd


class ScreenShareManager:
    def __init__(self, on_incoming_share: Callable[[str], None]):
        Gst.init(None)
        self.on_incoming_share = on_incoming_share
        self.pipeline: Optional[Gst.Pipeline] = None
        self.webrtcbin: Optional[Gst.Element] = None
        self.glib_loop = GLib.MainLoop()
        
        self.thread = threading.Thread(target=self.glib_loop.run, daemon=True)
        self.thread.start()

    async def _wait_for_ice_gathering(self, webrtcbin: Gst.Element):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        def on_state_changed(element, pspec):
            state = element.get_property('ice-gathering-state')
            if state == GstWebRTC.WebRTCICEGatheringState.COMPLETE:
                if not future.done(): loop.call_soon_threadsafe(future.set_result, True)
                    
        handler_id = webrtcbin.connect('notify::ice-gathering-state', on_state_changed)
        if webrtcbin.get_property('ice-gathering-state') == GstWebRTC.WebRTCICEGatheringState.COMPLETE:
            webrtcbin.disconnect(handler_id)
            return

        try: await asyncio.wait_for(future, timeout=3.0)
        except asyncio.TimeoutError: print("[WebRTC] ICE timeout. Proceeding...")
        finally: webrtcbin.disconnect(handler_id)

    async def start_signaling_server(self, host: str, port: int = SIGNALING_PORT):
        server = await asyncio.start_server(self._handle_signaling, host, port)
        print(f"[WebRTC] Signaling server listening on {host}:{port}")
        return server

    async def _handle_signaling(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        try:
            data = await reader.read(8192)
            if not data: return
                
            payload = json.loads(data.decode('utf-8'))
            if payload.get('type') == 'offer':
                self.on_incoming_share(payload.get('peer_id', 'Unknown'))
                self._create_receiving_pipeline()
                
                _, sdpmsg = GstSdp.sdp_message_new()
                GstSdp.sdp_message_parse_buffer(bytes(payload['sdp'], 'utf-8'), sdpmsg)
                res = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, sdpmsg)
                
                self.webrtcbin.emit('set-remote-description', res, None)
                
                loop = asyncio.get_running_loop()
                answer_future = loop.create_future()

                def on_answer_created(promise, *args):
                    reply = promise.get_reply()
                    answer = reply.get_value('answer')
                    if answer is None:
                        loop.call_soon_threadsafe(answer_future.set_exception, Exception("Failed to create answer"))
                        return
                    self.webrtcbin.emit('set-local-description', answer, None)
                    loop.call_soon_threadsafe(answer_future.set_result, True)

                promise = Gst.Promise.new_with_change_func(on_answer_created, None, None)
                self.webrtcbin.emit('create-answer', None, promise)
                await answer_future
                
                print("[WebRTC] Gathering network routing candidates...")
                await self._wait_for_ice_gathering(self.webrtcbin)
                
                sdp_text = self.webrtcbin.get_property('local-description').sdp.as_text()
                writer.write(json.dumps({'type': 'answer', 'sdp': sdp_text}).encode('utf-8'))
                await writer.drain()
        except Exception as e:
            print(f"[WebRTC] Signaling Error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    def _create_receiving_pipeline(self):
        self._cleanup()
        print("[WebRTC] Building receiver pipeline...")
        pipeline_str = "webrtcbin name=recvbin  rtpvp8depay name=depay ! vp8dec ! videoconvert ! autovideosink"
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.webrtcbin = self.pipeline.get_by_name('recvbin')
        depay = self.pipeline.get_by_name('depay')

        def on_pad_added(element, pad):
            if pad.get_direction() == Gst.PadDirection.SRC:
                sink_pad = depay.get_static_pad("sink")
                if not sink_pad.is_linked():
                    pad.link(sink_pad)
                    print("[WebRTC] Video pipeline successfully linked and playing.")

        self.webrtcbin.connect('pad-added', on_pad_added)
        self.pipeline.set_state(Gst.State.PLAYING)

    async def start_broadcasting(self, target_ip: str, my_peer_id: str) -> bool:
        self._cleanup()
        target_port = 49157 if target_ip == '127.0.0.1' else SIGNALING_PORT
        
        try:
            print("[Portal] Requesting screen access from Wayland...")
            portal = WaylandScreenCapture()
            
            # Extract BOTH the Node ID and the secure File Descriptor
            node_id, fd = await portal.get_pipewire_node_id_and_fd()
            
            print(f"[WebRTC] Connecting to {target_ip}:{target_port} to broadcast screen {node_id} via FD {fd}...")
            
            # THE FIX: Upgraded vp8enc parameters for high-definition, low-latency streaming
            pipeline_str = (
                f"pipewiresrc fd={fd} path={node_id} do-timestamp=true ! videoconvert ! "
                "vp8enc deadline=1 target-bitrate=5000000 cpu-used=4 end-usage=cbr threads=4 ! "
                "rtpvp8pay ! application/x-rtp,media=video,encoding-name=VP8,payload=97 ! "
                "webrtcbin name=sendbin"
            )
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.webrtcbin = self.pipeline.get_by_name('sendbin')
            
            loop = asyncio.get_running_loop()
            offer_future = loop.create_future()

            def on_offer_created(promise, *args):
                reply = promise.get_reply()
                offer = reply.get_value('offer')
                if offer is None:
                    loop.call_soon_threadsafe(offer_future.set_exception, Exception("Empty offer"))
                    return
                self.webrtcbin.emit('set-local-description', offer, None)
                loop.call_soon_threadsafe(offer_future.set_result, True)

            def on_negotiation_needed(element):
                promise = Gst.Promise.new_with_change_func(on_offer_created, None, None)
                element.emit('create-offer', None, promise)

            self.webrtcbin.connect('on-negotiation-needed', on_negotiation_needed)
            self.pipeline.set_state(Gst.State.PLAYING)

            await offer_future
            
            print("[WebRTC] Gathering network routing candidates...")
            await self._wait_for_ice_gathering(self.webrtcbin)
            sdp_text = self.webrtcbin.get_property('local-description').sdp.as_text()
            
            reader, writer = await asyncio.open_connection(target_ip, target_port)
            writer.write(json.dumps({'type': 'offer', 'peer_id': my_peer_id, 'sdp': sdp_text}).encode('utf-8'))
            await writer.drain()
            
            data = await reader.read(8192)
            response = json.loads(data.decode('utf-8'))
            if response.get('type') == 'answer':
                _, sdpmsg = GstSdp.sdp_message_new()
                GstSdp.sdp_message_parse_buffer(bytes(response['sdp'], 'utf-8'), sdpmsg)
                res = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
                
                self.webrtcbin.emit('set-remote-description', res, None)
                print("[WebRTC] Streaming established successfully!")
                
            writer.close()
            await writer.wait_closed()
            return True
            
        except Exception as e:
            print(f"[WebRTC/Portal] Broadcast error: {e}")
            self._cleanup()
            return False

    def stop_stream(self):
        self._cleanup()

    def _cleanup(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.webrtcbin = None