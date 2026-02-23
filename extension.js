// extension.js
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Import our custom panel module
import { ShareBridgePanel } from './src/panel.js';

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
        this._daemonProxy = null;
        this._signalIds = [];
    }

    async enable() {
        console.log(`[ShareBridge] Enabling extension ${this.uuid}`);

        // 1. Mount our custom UI Panel
        this._indicator = new ShareBridgePanel();
        Main.panel.addToStatusArea(this.uuid, this._indicator);

        try {
            // 2. Initialize D-Bus connection
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

            // 3. Connect signals for peer discovery and loss
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

        if (this._daemonProxy) {
            this._signalIds.forEach(id => this._daemonProxy.disconnectSignal(id));
            this._signalIds = [];
            this._daemonProxy = null;
        }

        // Properly unmount the UI to prevent memory leaks in GNOME Shell
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }

    _onPeerDiscovered(proxy, senderName, [peerJson]) {
        try {
            const peerData = JSON.parse(peerJson);
            if (this._indicator) {
                this._indicator.addPeer(peerData);
            }
        } catch (error) {
            console.error(`[ShareBridge] JSON Parse error: ${error.message}`);
        }
    }

    _onPeerLost(proxy, senderName, [peerId]) {
        if (this._indicator) {
            this._indicator.removePeer(peerId);
        }
    }
}