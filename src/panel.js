// src/panel.js
import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { pickFile } from './fileTransfer.js';

const PANEL_WIDTH = 400;

// =========================================================
// 1. TOP BAR INDICATOR
// =========================================================
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

        // Bypass standard menu popup and emit our own toggle signal
        this.connect('button-press-event', () => {
            this.emit('toggle-side-panel');
            return Clutter.EVENT_STOP;
        });
    }
});

// =========================================================
// 2. SLIDING SIDE PANEL CONTROLLER
// =========================================================
export class SidePanel {
    constructor(daemonProxy) {
        this.daemonProxy = daemonProxy;
        this.peers = new Map();
        this.isOpen = false;
        this.currentPeer = null;
        this.activeTransfers = new Map(); // Tracks progress bars

        // Main Drawer Container
        this.container = new St.BoxLayout({
            vertical: true,
            style_class: 'sharebridge-side-panel',
            reactive: true,
            x_expand: true,
            y_expand: true,
        });

        // Add to global UI group to sit above all windows
        Main.layoutManager.uiGroup.add_child(this.container);
        
        // Initial setup and monitor tracking
        this._updateGeometry();
        this._monitorsChangedId = Main.layoutManager.connect('monitors-changed', () => this._updateGeometry());

        this.showPeerList();
    }

    _updateGeometry() {
        const monitor = Main.layoutManager.primaryMonitor;
        const topPanelHeight = Main.layoutManager.panelBox.height;
        
        this.container.set_size(PANEL_WIDTH, monitor.height - topPanelHeight);
        // Position off-screen by default
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

    // --- PEER MANAGEMENT ---
    // --- PEER MANAGEMENT ---
    addPeer(peerData) {
        // Fallback key: Use id, device_id, name, or a random string to guarantee uniqueness
        const peerKey = peerData.id || peerData.device_id || peerData.name || Math.random().toString();
        
        console.log(`[ShareBridge UI] Storing peer in Map: ${peerData.name} under key: ${peerKey}`);
        this.peers.set(peerKey, peerData);
        console.log(`[ShareBridge UI] Total peers in Map: ${this.peers.size}`);

        // Forcefully refresh the UI if we aren't currently inside a chat/file view
        if (!this.currentPeer) {
            this.showPeerList();
        }
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

    // =========================================================
    // SCREEN 1: PEER LIST
    // =========================================================
    showPeerList() {
        console.log(`[ShareBridge UI] Rendering Peer List. Current map size: ${this.peers.size}`);
        this.currentPeer = null;
        this.container.destroy_all_children();

        // Header
        const header = new St.BoxLayout({ style_class: 'sb-header', x_align: Clutter.ActorAlign.CENTER });
        header.add_child(new St.Label({ text: 'ShareBridge Peers', style_class: 'sb-header-title' }));
        this.container.add_child(header);

        // Scrollable List
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
                console.log(`[ShareBridge UI] Drawing UI row for peer: ${peer.name}`);
                
                const row = new St.Button({ style_class: 'sb-peer-row', x_expand: true, reactive: true });
                const rowContent = new St.BoxLayout({ vertical: false });
                rowContent.add_child(new St.Icon({ icon_name: 'computer-symbolic', icon_size: 24, style: 'margin-right: 15px;' }));
                rowContent.add_child(new St.Label({ text: peer.name, style_class: 'sb-peer-name', y_align: Clutter.ActorAlign.CENTER }));
                
                row.set_child(rowContent);
                row.connect('clicked', () => this.showPeerDetail(peer));
                listLayout.add_child(row);
            }
        }
    }

    // =========================================================
    // SCREEN 2: PEER DETAIL & NAVIGATION
    // =========================================================
    showPeerDetail(peer) {
        try {
            console.log(`[ShareBridge UI] Opening detail view for peer: ${peer.name}`);
            this.currentPeer = peer;
            this.container.destroy_all_children();

            // 1. Header with Back Button
            const header = new St.BoxLayout({ style_class: 'sb-header', vertical: false });
            const backBtn = new St.Button({ style_class: 'sb-icon-button', reactive: true });
            
            // Fixed Icon syntax for broader GNOME compatibility
            backBtn.set_child(new St.Icon({ icon_name: 'go-previous-symbolic', style: 'icon-size: 20px;' }));
            backBtn.connect('clicked', () => this.showPeerList());
            
            const title = new St.Label({ text: peer.name || 'Unknown Peer', style_class: 'sb-header-title', x_expand: true, y_align: Clutter.ActorAlign.CENTER });
            header.add_child(backBtn);
            header.add_child(title);
            this.container.add_child(header);

            // 2. Navigation Bar
            const navBar = new St.BoxLayout({ style_class: 'sb-nav-bar', x_expand: true });
            this.contentStack = new St.BoxLayout({ vertical: true, x_expand: true, y_expand: true });

            const tabs = [
                { id: 'file', label: 'Files Share', buildFn: () => this._safeBuildView('_buildFileTransfer', peer) },
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
                
                // Default to File tab
                if (tab.id === 'file') {
                    activeTabBtn = btn;
                    btn.add_style_pseudo_class('checked');
                    this.contentStack.add_child(tab.buildFn());
                }
            });

            this.container.add_child(navBar);
            this.container.add_child(this.contentStack);
            console.log(`[ShareBridge UI] Successfully rendered detail view`);
            
        } catch (error) {
            console.error(`[ShareBridge UI] FATAL ERROR in showPeerDetail: ${error.message}`);
            // Physically show the error on the panel instead of just going blank
            const errorLabel = new St.Label({ 
                text: `UI Crash:\n${error.message}`, 
                style: 'color: #ff5555; padding: 20px; font-weight: bold;',
                x_expand: true, y_expand: true
            });
            this.container.add_child(errorLabel);
        }
    }

    // Safety Wrapper for Tabs
    _safeBuildView(methodName, peer) {
        try {
            console.log(`[ShareBridge UI] Building tab: ${methodName}`);
            return this[methodName](peer);
        } catch (error) {
            console.error(`[ShareBridge UI] FATAL ERROR in ${methodName}: ${error.message}`);
            const errorBox = new St.BoxLayout({ vertical: true, style: 'padding: 20px;' });
            errorBox.add_child(new St.Label({ text: `Failed to load tab: ${methodName}`, style: 'font-weight: bold; color: #ff5555;' }));
            errorBox.add_child(new St.Label({ text: error.message }));
            return errorBox;
        }
    }

    // =========================================================
    // SCREEN 3: FEATURE VIEWS
    // =========================================================

    // --- FILE TRANSFER TAB ---
    // --- FILE TRANSFER TAB ---
    _buildFileTransfer(peer) {
        const layout = new St.BoxLayout({ vertical: true, style_class: 'sb-content-area', x_expand: true, y_expand: true });
        
        const sendBtn = new St.Button({ label: 'Select File to Send', style_class: 'sb-btn-primary', x_expand: true, reactive: true });
        const progressContainer = new St.BoxLayout({ vertical: true, style: 'margin-top: 20px;', x_expand: true });

        // Safely extract the ID
        const targetId = peer.id || peer.device_id || peer.name;

        sendBtn.connect('clicked', async () => {
            const filePath = await pickFile();
            if (filePath && this.daemonProxy) {
                Main.notify('ShareBridge', `Initiating file transfer to ${peer.name}...`);
                
                // Track progress UI
                const pBg = new St.BoxLayout({ style_class: 'sb-progress-bg', x_expand: true });
                const pFill = new St.BoxLayout({ style_class: 'sb-progress-fill' });
                pFill.set_width(0);
                pBg.add_child(pFill);
                progressContainer.add_child(new St.Label({ text: `Sending: ${filePath.split('/').pop()}`, style: 'font-size: 0.9em; margin-top:10px;' }));
                progressContainer.add_child(pBg);

                // FIX: Use targetId instead of peer.id
                this.daemonProxy.SendFileRemote(targetId, filePath, (result, err) => {
                    if (err) {
                        console.error(`[ShareBridge] File Transfer Error: ${err.message}`);
                        Main.notify('ShareBridge', 'Failed to start file transfer.');
                    } else if (result && result[0]) {
                        const transferId = result[0]; // Capture ID returned from Python
                        this.activeTransfers.set(transferId, pFill);
                    }
                });
            }
        });

        layout.add_child(sendBtn);
        layout.add_child(progressContainer);
        return layout;
    }

    updateFileProgress(transferId, percentage) {
        const pFill = this.activeTransfers.get(transferId);
        if (pFill) {
            // Assuming full width is roughly PANEL_WIDTH - padding (30px)
            const maxWidth = PANEL_WIDTH - 30;
            pFill.ease({
                width: (percentage / 100) * maxWidth,
                duration: 200,
                mode: Clutter.AnimationMode.EASE_OUT_QUAD
            });
            if (percentage >= 100) this.activeTransfers.delete(transferId);
        }
    }

    // --- SCREEN SHARE TAB ---
    _buildScreenShare(peer) {
        const layout = new St.BoxLayout({ vertical: true, style_class: 'sb-content-area', x_expand: true, y_expand: true, x_align: Clutter.ActorAlign.CENTER });
        
        const startBtn = new St.Button({ label: 'Start Broadcasting Screen', style_class: 'sb-btn-primary', x_expand: true, reactive: true });
const stopBtn = new St.Button({ label: 'Stop Broadcasting', style_class: 'sb-btn-danger', x_expand: true, reactive: true, style: 'margin-top: 10px;' });

        // Safely extract the ID
        const targetId = peer.id || peer.device_id || peer.name;

        startBtn.connect('clicked', () => {
            Main.notify('ShareBridge', 'Starting broadcast. Please select a screen via GNOME Prompt.');
            
            // FIX: Use targetId instead of peer.id
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