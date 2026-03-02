// extension.js
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import { ShareBridgePanel, SidePanel } from './src/panel.js';
import { ShareBridgeIndicator } from './src/quickSettings.js';

// Removed all Chat methods and signals
const DBUS_INTERFACE_XML = `
<node>
  <interface name="org.gnome.shell.extensions.sharebridge.Daemon">
    <method name="GetPeers"><arg type="s" name="peers_json" direction="out"/></method>
    <method name="SendFile">
      <arg type="s" name="peer_id" direction="in"/><arg type="s" name="file_path" direction="in"/><arg type="s" name="transfer_id" direction="out"/>
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
    <signal name="IncomingScreenShare"><arg type="s" name="peer_id"/></signal>
  </interface>
</node>`;

const DaemonProxyWrapper = Gio.DBusProxy.makeProxyWrapper(DBUS_INTERFACE_XML);

export default class ShareBridgeExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._indicator = null;
        this._quickSettings = null;
        this._sidePanel = null;
        this._daemonProxy = null;
        this._signalIds = [];
        this._peerCount = 0;
        this._initTimeoutId = null;
    }

    enable() {
        console.log(`[ShareBridge] Enabling extension ${this.uuid}`);

        this._indicator = new ShareBridgePanel();
        Main.panel.addToStatusArea(this.uuid, this._indicator);

        this._quickSettings = new ShareBridgeIndicator();
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._quickSettings);

        // Start the Python Daemon
        this._startDaemon();

        // Delay D-Bus binding slightly to give Python time to acquire the bus name
        this._initTimeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
            this._initializeDBus();
            return GLib.SOURCE_REMOVE;
        });
    }

    _initializeDBus() {
        try {
            this._daemonProxy = new DaemonProxyWrapper(
                Gio.DBus.session,
                'org.gnome.shell.extensions.sharebridge',
                '/org/gnome/shell/extensions/sharebridge/Daemon'
            );

            this._sidePanel = new SidePanel(this._daemonProxy);

            this._indicator.connect('toggle-side-panel', () => {
                this._sidePanel.toggle();
            });

            this._signalIds.push(
                this._daemonProxy.connectSignal('PeerDiscovered', (proxy, senderName, [peerJson]) => this._addPeer(JSON.parse(peerJson))),
                this._daemonProxy.connectSignal('PeerLost', (proxy, senderName, [peerId]) => this._removePeer(peerId)),
                
                this._daemonProxy.connectSignal('FileProgress', (proxy, senderName, [transferId, percentage]) => {
                    this._sidePanel.updateFileProgress(transferId, percentage);
                    if (percentage >= 100) Main.notify('ShareBridge', 'File transfer successfully completed!');
                }),
                
                this._daemonProxy.connectSignal('IncomingScreenShare', (proxy, senderName, [peerId]) => {
                    Main.notify('ShareBridge', 'Incoming screen share! Opening viewer window...');
                })
            );

            this._daemonProxy.GetPeersRemote((result, error) => {
                if (error) return console.error(`[ShareBridge] D-Bus GetPeers Error: ${error.message}`);
                if (result && result[0]) {
                    try {
                        let parsedData = JSON.parse(result[0]);
                        let peersArray = Array.isArray(parsedData) ? parsedData : Object.values(parsedData);
                        peersArray.forEach(peer => this._addPeer(peer));
                    } catch (e) {
                        console.error(`[ShareBridge] Error parsing GetPeers: ${e.message}`);
                    }
                }
            });

        } catch (error) {
            console.error(`[ShareBridge] Fatal D-Bus error: ${error.message}`);
        }
    }

    disable() {
        if (this._initTimeoutId) {
            GLib.source_remove(this._initTimeoutId);
            this._initTimeoutId = null;
        }
        if (this._sidePanel) {
            this._sidePanel.destroy();
            this._sidePanel = null;
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
        this._stopDaemon();
        this._peerCount = 0;
    }

    _startDaemon() {
        try {
            const daemonPath = this.dir.get_child('daemon').get_child('sharebridge-daemon.py').get_path();
            const venvPython = this.dir.get_child('daemon').get_child('venv').get_child('bin').get_child('python3').get_path();
            
            // Prefer virtual environment python over system python to ensure dependencies are found
            const pythonExec = GLib.file_test(venvPython, GLib.FileTest.EXISTS) ? venvPython : 'python3';

            this._daemonProc = Gio.Subprocess.new(
                [pythonExec, daemonPath],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );
            console.log('[ShareBridge] Daemon started successfully.');
        } catch (e) {
            console.error(`[ShareBridge] Failed to start daemon: ${e.message}`);
        }
    }

    _stopDaemon() {
        if (this._daemonProc) {
            this._daemonProc.force_exit();
            this._daemonProc = null;
            console.log('[ShareBridge] Daemon stopped.');
        }
    }

    _addPeer(peerData) {
        if (this._sidePanel) this._sidePanel.addPeer(peerData);
        if (this._quickSettings && this._quickSettings.toggle) {
            this._peerCount++;
            this._quickSettings.toggle.updatePeerCount(this._peerCount);
        }
    }

    _removePeer(peerId) {
        if (this._sidePanel) this._sidePanel.removePeer(peerId);
        if (this._quickSettings && this._peerCount > 0) {
            this._peerCount--;
            this._quickSettings.toggle.updatePeerCount(this._peerCount);
        }
    }
}