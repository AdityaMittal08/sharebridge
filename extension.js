// extension.js
import Gio from 'gi://Gio';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import { ShareBridgePanel } from './src/panel.js';
import { ShareBridgeIndicator } from './src/quickSettings.js';
import { ChatDialog } from './src/chatDialog.js';

const DBUS_INTERFACE_XML = `
<node>
  <interface name="org.gnome.shell.extensions.sharebridge.Daemon">
    <method name="GetPeers"><arg type="s" name="peers_json" direction="out"/></method>
    <method name="SendFile">
      <arg type="s" name="peer_id" direction="in"/><arg type="s" name="file_path" direction="in"/><arg type="s" name="transfer_id" direction="out"/>
    </method>
    <method name="SendMessage">
      <arg type="s" name="peer_id" direction="in"/><arg type="s" name="message" direction="in"/><arg type="b" name="success" direction="out"/>
    </method>
    <method name="GetChatHistory">
      <arg type="s" name="peer_id" direction="in"/><arg type="s" name="history_json" direction="out"/>
    </method>
    <method name="StartScreenShare">
      <arg type="s" name="peer_id" direction="in"/><arg type="b" name="success" direction="out"/>
    </method>
    <method name="StopScreenShare">
      <arg type="b" name="success" direction="out"/>
    </method>
    <signal name="PeerDiscovered"><arg type="s" name="peer_json"/></signal>
    <signal name="PeerLost"><arg type="s" name="peer_id"/></signal>
    <signal name="FileProgress"><arg type="s" name="transfer_id"/><arg type="d" name="percentage"/></signal>
    <signal name="NewMessage"><arg type="s" name="peer_id"/><arg type="s" name="message"/></signal>
    <signal name="IncomingScreenShare"><arg type="s" name="peer_id"/></signal>
  </interface>
</node>`;

const DaemonProxyWrapper = Gio.DBusProxy.makeProxyWrapper(DBUS_INTERFACE_XML);

export default class ShareBridgeExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._indicator = null;
        this._quickSettings = null;
        this._daemonProxy = null;
        this._signalIds = [];
        this._peerCount = 0;
        this._activeChatDialog = null; 
    }

    enable() {
        console.log(`[ShareBridge] Enabling extension ${this.uuid}`);

        this._indicator = new ShareBridgePanel();
        Main.panel.addToStatusArea(this.uuid, this._indicator);

        this._quickSettings = new ShareBridgeIndicator();
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._quickSettings);

        this._indicator.connect('file-send-requested', (source, peerId, filePath) => {
            if (this._daemonProxy) {
                Main.notify('ShareBridge', `Initiating file transfer...`);
                this._daemonProxy.SendFileRemote(peerId, filePath, () => {});
            }
        });

        this._indicator.connect('chat-requested', (source, peerId, peerName) => {
            if (this._activeChatDialog) this._activeChatDialog.close();
            this._activeChatDialog = new ChatDialog(peerId, peerName, this._daemonProxy);
            this._activeChatDialog.connect('closed', () => { this._activeChatDialog = null; });
            this._activeChatDialog.open();
        });

        this._indicator.connect('screen-share-requested', (source, peerId) => {
            if (this._daemonProxy) {
                Main.notify('ShareBridge', 'Starting screen share. Please select the screen to broadcast when prompted by GNOME.');
                this._daemonProxy.StartScreenShareRemote(peerId, () => {});
            }
        });

        this._indicator.connect('screen-share-stop-requested', () => {
            if (this._daemonProxy) {
                this._daemonProxy.StopScreenShareRemote(() => {});
                Main.notify('ShareBridge', 'Screen sharing stopped.');
            }
        });

        try {
            this._daemonProxy = new DaemonProxyWrapper(
                Gio.DBus.session,
                'org.gnome.shell.extensions.sharebridge',
                '/org/gnome/shell/extensions/sharebridge/Daemon'
            );

            this._signalIds.push(
                this._daemonProxy.connectSignal('PeerDiscovered', (proxy, senderName, [peerJson]) => this._addPeerToUI(JSON.parse(peerJson))),
                this._daemonProxy.connectSignal('PeerLost', (proxy, senderName, [peerId]) => this._removePeerFromUI(peerId)),
                this._daemonProxy.connectSignal('FileProgress', (proxy, senderName, [transferId, percentage]) => {
                    if (percentage >= 100) Main.notify('ShareBridge', 'File transfer successfully completed!');
                }),
                this._daemonProxy.connectSignal('NewMessage', (proxy, senderName, [peerId, message]) => {
                    if (this._activeChatDialog && this._activeChatDialog.peerId === peerId) {
                        this._activeChatDialog.addMessage(false, message);
                    } else {
                        Main.notify('ShareBridge Message', message);
                    }
                }),
                this._daemonProxy.connectSignal('IncomingScreenShare', (proxy, senderName, [peerId]) => {
                    Main.notify('ShareBridge', 'Incoming screen share! Opening viewer window...');
                })
            );

            this._daemonProxy.GetPeersRemote((result, error) => {
                if (result && result[0]) JSON.parse(result[0]).forEach(peer => this._addPeerToUI(peer));
            });

        } catch (error) {
            console.error(`[ShareBridge] Fatal D-Bus error: ${error.message}`);
        }
    }

    disable() {
        if (this._activeChatDialog) {
            this._activeChatDialog.close();
            this._activeChatDialog = null;
        }
        if (this._daemonProxy) {
            this._signalIds.forEach(id => this._daemonProxy.disconnectSignal(id));
            this._signalIds = [];
            this._daemonProxy = null;
        }
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
        if (this._quickSettings) {
            this._quickSettings.destroy();
            this._quickSettings = null;
        }
        this._peerCount = 0;
    }

    _addPeerToUI(peerData) {
        if (this._indicator) this._indicator.addPeer(peerData);
        if (this._quickSettings) {
            this._peerCount++;
            this._quickSettings.toggle.updatePeerCount(this._peerCount);
        }
    }

    _removePeerFromUI(peerId) {
        if (this._indicator) this._indicator.removePeer(peerId);
        if (this._quickSettings && this._peerCount > 0) {
            this._peerCount--;
            this._quickSettings.toggle.updatePeerCount(this._peerCount);
        }
    }
}