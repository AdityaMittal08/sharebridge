// src/panel.js
import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { pickFile } from './fileTransfer.js';

const PANEL_WIDTH = 400;

export const ShareBridgePanel = GObject.registerClass({
    Signals: {
        'toggle-side-panel': {}
    }
}, class ShareBridgePanel extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'ShareBridge Indicator');
        this._icon = new St.Icon({
            icon_name: 'network-transmit-receive-symbolic',
            style_class: 'system-status-icon',
        });
        this.add_child(this._icon);

        this.connect('button-press-event', () => {
            this.emit('toggle-side-panel');
            return Clutter.EVENT_STOP;
        });
    }
});

export class SidePanel {
    constructor(daemonProxy) {
        this.daemonProxy = daemonProxy;
        this.peers = new Map();
        this.isOpen = false;
        this.currentPeer = null;
        this.activeTransfers = new Map();

        this.container = new St.BoxLayout({
            vertical: true,
            style_class: 'sharebridge-side-panel',
            reactive: true,
            x_expand: true,
            y_expand: true,
        });

        Main.layoutManager.uiGroup.add_child(this.container);
        
        this._updateGeometry();
        this._monitorsChangedId = Main.layoutManager.connect('monitors-changed', () => this._updateGeometry());

        this.showPeerList();
    }

    _updateGeometry() {
        const monitor = Main.layoutManager.primaryMonitor;
        const topPanelHeight = Main.layoutManager.panelBox.height;
        
        this.container.set_size(PANEL_WIDTH, monitor.height - topPanelHeight);
        this.container.set_position(
            this.isOpen ? monitor.width - PANEL_WIDTH : monitor.width,
            topPanelHeight
        );
    }

    toggle() {
        this.isOpen = !this.isOpen;
        const monitor = Main.layoutManager.primaryMonitor;
        const targetX = this.isOpen ? monitor.width - PANEL_WIDTH : monitor.width;

        this.container.ease({
            x: targetX,
            duration: 250,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
        });

        if (this.isOpen) {
            this.container.raise_top();
            if (!this.currentPeer) this.showPeerList();
        }
    }

    destroy() {
        if (this._monitorsChangedId) {
            Main.layoutManager.disconnect(this._monitorsChangedId);
        }
        this.container.destroy();
    }

    addPeer(peerData) {
        const peerKey = peerData.id || peerData.device_id || peerData.name || Math.random().toString();
        this.peers.set(peerKey, peerData);
        if (!this.currentPeer) this.showPeerList();
    }

    removePeer(peerId) {
        this.peers.delete(peerId);
        if (this.currentPeer && this.currentPeer.id === peerId) {
            this.currentPeer = null;
            this.showPeerList();
        } else if (!this.currentPeer) {
            this.showPeerList();
        }
    }

    showPeerList() {
        this.currentPeer = null;
        this.container.destroy_all_children();

        const header = new St.BoxLayout({ style_class: 'sb-header', x_align: Clutter.ActorAlign.CENTER });
        header.add_child(new St.Label({ text: 'ShareBridge Peers', style_class: 'sb-header-title' }));
        this.container.add_child(header);

        const scrollView = new St.ScrollView({
            x_expand: true, y_expand: true,
            vscrollbar_policy: St.PolicyType.AUTOMATIC,
            hscrollbar_policy: St.PolicyType.NEVER,
        });
        const listLayout = new St.BoxLayout({ vertical: true, style_class: 'sb-peer-list', x_expand: true });
        scrollView.set_child(listLayout);
        this.container.add_child(scrollView);

        if (this.peers.size === 0) {
            listLayout.add_child(new St.Label({ text: 'Scanning local network...', x_align: Clutter.ActorAlign.CENTER, style: 'opacity: 0.7; margin-top: 20px;' }));
        } else {
            for (const [id, peer] of this.peers.entries()) {
                const row = new St.Button({ style_class: 'sb-peer-row', x_expand: true, reactive: true });
               const rowContent = new St.BoxLayout({ vertical: false });
                rowContent.add_child(new St.Icon({ icon_name: 'computer-symbolic', icon_size: 24, style: 'margin-right: 15px;' }));

                // Add fallback to IP address if name is missing
                const safeName = peer.name ? peer.name : `Unknown (${peer.ip || 'No IP'})`;
                rowContent.add_child(new St.Label({ text: safeName, style_class: 'sb-peer-name', y_align: Clutter.ActorAlign.CENTER }));
                
                row.set_child(rowContent);
                row.connect('clicked', () => this.showPeerDetail(peer));
                listLayout.add_child(row);
            }
        }
    }

    showPeerDetail(peer) {
        try {
            this.currentPeer = peer;
            this.container.destroy_all_children();

            const header = new St.BoxLayout({ style_class: 'sb-header', vertical: false });
            const backBtn = new St.Button({ style_class: 'sb-icon-button', reactive: true });
            backBtn.set_child(new St.Icon({ icon_name: 'go-previous-symbolic', style: 'icon-size: 20px;' }));
            backBtn.connect('clicked', () => this.showPeerList());
            
            const title = new St.Label({ text: peer.name || 'Unknown Peer', style_class: 'sb-header-title', x_expand: true, y_align: Clutter.ActorAlign.CENTER });
            header.add_child(backBtn);
            header.add_child(title);
            this.container.add_child(header);

            const navBar = new St.BoxLayout({ style_class: 'sb-nav-bar', x_expand: true });
            this.contentStack = new St.BoxLayout({ vertical: true, x_expand: true, y_expand: true });

            const tabs = [
                { id: 'file', label: 'File Share', buildFn: () => this._safeBuildView('_buildFileTransfer', peer) },
                { id: 'screen', label: 'Screen Share', buildFn: () => this._safeBuildView('_buildScreenShare', peer) }
            ];

            let activeTabBtn = null;

            tabs.forEach(tab => {
                const btn = new St.Button({ label: tab.label, style_class: 'sb-nav-tab', x_expand: true, reactive: true });
                btn.connect('clicked', () => {
                    if (activeTabBtn) activeTabBtn.remove_style_pseudo_class('checked');
                    btn.add_style_pseudo_class('checked');
                    activeTabBtn = btn;
                    
                    this.contentStack.destroy_all_children();
                    this.contentStack.add_child(tab.buildFn());
                });
                navBar.add_child(btn);
                
                if (tab.id === 'file') {
                    activeTabBtn = btn;
                    btn.add_style_pseudo_class('checked');
                    this.contentStack.add_child(tab.buildFn());
                }
            });

            this.container.add_child(navBar);
            this.container.add_child(this.contentStack);
            
        } catch (error) {
            console.error(`[ShareBridge UI] FATAL ERROR in showPeerDetail: ${error.message}`);
            const errorLabel = new St.Label({ text: `UI Crash:\n${error.message}`, style: 'color: #ff5555; padding: 20px; font-weight: bold;', x_expand: true, y_expand: true });
            this.container.add_child(errorLabel);
        }
    }

    _safeBuildView(methodName, peer) {
        try {
            return this[methodName](peer);
        } catch (error) {
            const errorBox = new St.BoxLayout({ vertical: true, style: 'padding: 20px;' });
            errorBox.add_child(new St.Label({ text: `Failed to load tab`, style: 'font-weight: bold; color: #ff5555;' }));
            errorBox.add_child(new St.Label({ text: error.message }));
            return errorBox;
        }
    }

    _buildFileTransfer(peer) {
        const layout = new St.BoxLayout({ vertical: true, style_class: 'sb-content-area', x_expand: true, y_expand: true });
        const sendBtn = new St.Button({ label: 'Select File to Send', style_class: 'sb-btn-primary', x_expand: true, reactive: true });
        const progressContainer = new St.BoxLayout({ vertical: true, style: 'margin-top: 20px;', x_expand: true });

        const targetId = peer.id || peer.device_id || peer.name;

        sendBtn.connect('clicked', async () => {
            const filePath = await pickFile();
            if (filePath && this.daemonProxy) {
                Main.notify('ShareBridge', `Initiating file transfer to ${peer.name}...`);
                
                // Pre-generate Transfer ID to fix the race condition
                const transferId = GLib.uuid_string_random();
                
                const transferBox = new St.BoxLayout({ vertical: true, x_expand: true });
                const pBg = new St.BoxLayout({ style_class: 'sb-progress-bg', x_expand: true });
                
                // FIX: Use St.Widget instead of St.BoxLayout to prevent auto-stretching.
                // Strictly lock the initial inline style to 0px width.
                const pFill = new St.Widget({ style_class: 'sb-progress-fill' });
                pFill.style = 'width: 0px; min-width: 0px; background-color: #3584e4; border-radius: 5px; height: 10px;';
                pFill.set_width(0);
                
                pBg.add_child(pFill);
                
                transferBox.add_child(new St.Label({ text: `Sending: ${filePath.split('/').pop()}`, style: 'font-size: 0.9em; margin-top:10px;' }));
                transferBox.add_child(pBg);
                progressContainer.add_child(transferBox);

                // Track before making the RPC call
                this.activeTransfers.set(transferId, { fill: pFill, box: transferBox });

                this.daemonProxy.SendFileRemote(targetId, filePath, transferId, (result, err) => {
                    if (err) {
                        transferBox.destroy(); 
                        this.activeTransfers.delete(transferId);
                        console.error(`[ShareBridge] Failed to send file: ${err.message}`);
                    }
                });
            }
        });

        layout.add_child(sendBtn);
        layout.add_child(progressContainer);
        return layout;
    }

    updateFileProgress(transferId, percentage) {
        const transfer = this.activeTransfers.get(transferId);
        if (transfer) {
            const maxWidth = PANEL_WIDTH - 30;
            transfer.fill.ease({
                width: (percentage / 100) * maxWidth,
                duration: 200,
                mode: Clutter.AnimationMode.EASE_OUT_QUAD
            });

            if (percentage >= 100) {
                GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
                    if (transfer.box) transfer.box.destroy();
                    this.activeTransfers.delete(transferId);
                    return GLib.SOURCE_REMOVE;
                });
            }
        }
    }

    _buildScreenShare(peer) {
        const layout = new St.BoxLayout({ vertical: true, style_class: 'sb-content-area', x_expand: true, y_expand: true, x_align: Clutter.ActorAlign.CENTER });
        const startBtn = new St.Button({ label: 'Start Broadcasting Screen', style_class: 'sb-btn-primary', x_expand: true, reactive: true });
        const stopBtn = new St.Button({ label: 'Stop Broadcasting', style_class: 'sb-btn-danger', x_expand: true, reactive: true, style: 'margin-top: 10px;' });

        const targetId = peer.id || peer.device_id || peer.name;

        startBtn.connect('clicked', () => {
            Main.notify('ShareBridge', 'Starting broadcast. Please select a screen via GNOME Prompt.');
            this.daemonProxy.StartScreenShareRemote(targetId, (result, err) => {
                if (err) console.error(`[ShareBridge] Screen Share Error: ${err.message}`);
            });
        });

        stopBtn.connect('clicked', () => {
            Main.notify('ShareBridge', 'Screen broadcast stopped.');
            this.daemonProxy.StopScreenShareRemote((result, err) => {
                 if (err) console.error(`[ShareBridge] Stop Screen Share Error: ${err.message}`);
            });
        });

        layout.add_child(new St.Label({ text: 'Share your screen securely via PipeWire & WebRTC.', style: 'margin-bottom: 20px; text-align: center; opacity: 0.8;', x_expand: true }));
        layout.add_child(startBtn);
        layout.add_child(stopBtn);
        
        return layout;
    }
}