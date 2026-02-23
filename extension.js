// extension.js
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Import our custom UI modules
import { ShareBridgePanel } from './src/panel.js';
import { ShareBridgeIndicator } from './src/quickSettings.js'; // NEW

const DBUS_INTERFACE_XML = `
<node>
  <interface name="org.gnome.shell.extensions.sharebridge.Daemon">
    <method name="GetPeers">
      <arg type="s" name="peers_json" direction="out"/>
    </method>
    <signal name="PeerDiscovered">
      <arg type="s" name="peer_json"/>
    </signal>
    <signal name="PeerLost">
      <arg type="s" name="peer_id"/>
    </signal>
  </interface>
</node>`;

const DaemonProxyInfo = Gio.DBusInterfaceInfo.new_for_xml(DBUS_INTERFACE_XML);

export default class ShareBridgeExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._indicator = null;
        this._quickSettings = null; // NEW
        this._daemonProxy = null;
        this._signalIds = [];
        this._peerCount = 0; // NEW: track peers for the Quick Settings UI
    }

    async enable() {
        console.log(`[ShareBridge] Enabling extension ${this.uuid}`);

        // 1. Mount the Top Bar Panel Indicator
        this._indicator = new ShareBridgePanel();
        Main.panel.addToStatusArea(this.uuid, this._indicator);

        // 2. Mount the Quick Settings Tile (NEW)
        this._quickSettings = new ShareBridgeIndicator();
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._quickSettings);

        try {
            // 3. Initialize D-Bus connection
            this._daemonProxy = new Gio.DBusProxy({
                g_connection: Gio.DBus.session,
                g_interface_name: 'org.gnome.shell.extensions.sharebridge.Daemon',
                g_interface_info: DaemonProxyInfo,
                g_name: 'org.gnome.shell.extensions.sharebridge',
                g_object_path: '/org/gnome/shell/extensions/sharebridge/Daemon',
                g_flags: Gio.DBusProxyFlags.NONE
            });

            await this._daemonProxy.init_async(GLib.PRIORITY_DEFAULT, null);
            console.log('[ShareBridge] Connected to Python Daemon via D-Bus');

            // 4. Connect signals for peer discovery and loss
            const discoveredId = this._daemonProxy.connectSignal('PeerDiscovered', 
                this._onPeerDiscovered.bind(this)
            );
            const lostId = this._daemonProxy.connectSignal('PeerLost', 
                this._onPeerLost.bind(this)
            );
            this._signalIds.push(discoveredId, lostId);

        } catch (error) {
            console.warn(`[ShareBridge] D-Bus init failed (daemon likely offline): ${error.message}`);
        }
    }

    disable() {
        console.log(`[ShareBridge] Disabling extension ${this.uuid}`);

        // 1. Clean up D-Bus signals
        if (this._daemonProxy) {
            this._signalIds.forEach(id => this._daemonProxy.disconnectSignal(id));
            this._signalIds = [];
            this._daemonProxy = null;
        }

        // 2. Unmount Top Bar Indicator
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }

        // 3. Unmount Quick Settings Tile safely (NEW)
        if (this._quickSettings) {
            this._quickSettings.destroy();
            this._quickSettings = null;
        }
        
        this._peerCount = 0;
    }

    _onPeerDiscovered(proxy, senderName, [peerJson]) {
        try {
            const peerData = JSON.parse(peerJson);
            
            // Update Top Bar Menu
            if (this._indicator) {
                this._indicator.addPeer(peerData);
            }
            
            // Update Quick Settings Subtitle
            if (this._quickSettings) {
                this._peerCount++;
                this._quickSettings.toggle.updatePeerCount(this._peerCount);
            }
        } catch (error) {
            console.error(`[ShareBridge] JSON Parse error: ${error.message}`);
        }
    }

    _onPeerLost(proxy, senderName, [peerId]) {
        // Update Top Bar Menu
        if (this._indicator) {
            this._indicator.removePeer(peerId);
        }

        // Update Quick Settings Subtitle
        if (this._quickSettings && this._peerCount > 0) {
            this._peerCount--;
            this._quickSettings.toggle.updatePeerCount(this._peerCount);
        }
    }
}