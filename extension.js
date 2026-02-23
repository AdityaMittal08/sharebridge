// extension.js
import Gio from 'gi://Gio';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import { ShareBridgePanel } from './src/panel.js';
import { ShareBridgeIndicator } from './src/quickSettings.js';

const DBUS_INTERFACE_XML = `
<node>
  <interface name="org.gnome.shell.extensions.sharebridge.Daemon">
    <method name="GetPeers">
      <arg type="s" name="peers_json" direction="out"/>
    </method>
    <method name="SendFile">
      <arg type="s" name="peer_id" direction="in"/>
      <arg type="s" name="file_path" direction="in"/>
      <arg type="s" name="transfer_id" direction="out"/>
    </method>
    <signal name="PeerDiscovered">
      <arg type="s" name="peer_json"/>
    </signal>
    <signal name="PeerLost">
      <arg type="s" name="peer_id"/>
    </signal>
    <signal name="FileProgress">
      <arg type="s" name="transfer_id"/>
      <arg type="d" name="percentage"/>
    </signal>
  </interface>
</node>`;

// THE FIX: Use makeProxyWrapper to properly generate DBus bindings
const DaemonProxyWrapper = Gio.DBusProxy.makeProxyWrapper(DBUS_INTERFACE_XML);

export default class ShareBridgeExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._indicator = null;
        this._quickSettings = null;
        this._daemonProxy = null;
        this._signalIds = [];
        this._peerCount = 0;
    }

    enable() {
        console.log(`[ShareBridge] Enabling extension ${this.uuid}`);

        this._indicator = new ShareBridgePanel();
        Main.panel.addToStatusArea(this.uuid, this._indicator);

        this._quickSettings = new ShareBridgeIndicator();
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._quickSettings);

        this._indicator.connect('file-send-requested', (source, peerId, filePath) => {
            this._initiateFileTransfer(peerId, filePath);
        });

        try {
            // Instantiate the Wrapper
            this._daemonProxy = new DaemonProxyWrapper(
                Gio.DBus.session,
                'org.gnome.shell.extensions.sharebridge',
                '/org/gnome/shell/extensions/sharebridge/Daemon'
            );

            console.log('[ShareBridge] Connected to Python Daemon via D-Bus Wrapper');

            // Connect Signals (This now works safely!)
            this._signalIds.push(
                this._daemonProxy.connectSignal('PeerDiscovered', this._onPeerDiscovered.bind(this)),
                this._daemonProxy.connectSignal('PeerLost', this._onPeerLost.bind(this)),
                this._daemonProxy.connectSignal('FileProgress', this._onFileProgress.bind(this))
            );

            // Fetch any peers that the Python daemon found before the UI booted up
            this._daemonProxy.GetPeersRemote((result, error) => {
                if (error) {
                    console.warn(`[ShareBridge] Could not fetch initial peers: ${error.message}`);
                    return;
                }
                if (result && result[0]) {
                    try {
                        const peersList = JSON.parse(result[0]);
                        peersList.forEach(peer => this._addPeerToUI(peer));
                    } catch (e) {
                        console.error(`[ShareBridge] JSON Parse error on startup: ${e.message}`);
                    }
                }
            });

        } catch (error) {
            console.error(`[ShareBridge] Fatal D-Bus error: ${error.message}`);
        }
    }

    disable() {
        console.log(`[ShareBridge] Disabling extension ${this.uuid}`);

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

    _initiateFileTransfer(peerId, filePath) {
        if (!this._daemonProxy) return;
        try {
            Main.notify('ShareBridge', `Initiating file transfer...`);
            // Call the Python method remotely
            this._daemonProxy.SendFileRemote(peerId, filePath, (result, error) => {
                if (error) console.error(`[ShareBridge] SendFile failed: ${error.message}`);
            });
        } catch (error) {
            console.error(`[ShareBridge] Failed to trigger transfer: ${error.message}`);
        }
    }

    _onFileProgress(proxy, senderName, [transferId, percentage]) {
        if (percentage >= 100) {
            Main.notify('ShareBridge', 'File transfer successfully completed!');
        }
    }

    _onPeerDiscovered(proxy, senderName, [peerJson]) {
        try {
            const peerData = JSON.parse(peerJson);
            this._addPeerToUI(peerData);
        } catch (error) {
            console.error(`[ShareBridge] Error parsing discovered peer: ${error.message}`);
        }
    }

    _addPeerToUI(peerData) {
        if (this._indicator) this._indicator.addPeer(peerData);
        if (this._quickSettings) {
            this._peerCount++;
            this._quickSettings.toggle.updatePeerCount(this._peerCount);
        }
    }

    _onPeerLost(proxy, senderName, [peerId]) {
        if (this._indicator) this._indicator.removePeer(peerId);
        if (this._quickSettings && this._peerCount > 0) {
            this._peerCount--;
            this._quickSettings.toggle.updatePeerCount(this._peerCount);
        }
    }
}