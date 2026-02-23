// src/panel.js
import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

export const ShareBridgePanel = GObject.registerClass(
    class ShareBridgePanel extends PanelMenu.Button {
        _init() {
            // 0.0 specifies center alignment in the panel, string is for accessibility
            super._init(0.0, 'ShareBridge Indicator');

            // 1. Set up the Top Bar Icon
            this._icon = new St.Icon({
                icon_name: 'network-transmit-receive-symbolic',
                style_class: 'system-status-icon',
            });
            this.add_child(this._icon);

            // 2. State management for network peers
            this._peers = new Map();

            // 3. Construct the UI tree
            this._buildMenu();
        }

        _buildMenu() {
            // --- Header Section ---
            this._headerItem = new PopupMenu.PopupMenuItem('ShareBridge', { reactive: false });
            this._headerItem.label.get_clutter_text().set_markup('<b>ShareBridge</b>');
            this.menu.addMenuItem(this._headerItem);

            this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

            // --- Dynamic Peer List Section ---
            this._peerSection = new PopupMenu.PopupMenuSection();
            this.menu.addMenuItem(this._peerSection);
            
            this._noPeersItem = new PopupMenu.PopupMenuItem('Scanning local network...', { reactive: false });
            this._peerSection.addMenuItem(this._noPeersItem);

            this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

            // --- Global Actions Section ---
            this._settingsItem = new PopupMenu.PopupMenuItem('Preferences');
            this._settingsItem.connect('activate', () => {
                // We will wire this to Adw.PreferencesWindow in Step 12
                console.log('[ShareBridge] Preferences clicked');
            });
            this.menu.addMenuItem(this._settingsItem);
        }

        /**
         * Dynamically adds a peer to the UI
         * @param {Object} peerData - { id: string, name: string, ip: string }
         */
        addPeer(peerData) {
            // Clear placeholder state if needed
            if (this._noPeersItem) {
                this._noPeersItem.destroy();
                this._noPeersItem = null;
            }

            // Prevent duplicates
            if (this._peers.has(peerData.id)) return;

            // Create a collapsible sub-menu for this specific peer
            const peerSubMenu = new PopupMenu.PopupSubMenuMenuItem(peerData.name);
            peerSubMenu.icon.icon_name = 'avatar-default-symbolic';

            // Action: Send File
            const sendFileItem = new PopupMenu.PopupMenuItem('Send File...');
            sendFileItem.connect('activate', () => {
                console.log(`[ShareBridge] Initiating file send to ${peerData.name}`);
                // Step 7 logic will go here
            });
            peerSubMenu.menu.addMenuItem(sendFileItem);

            // Action: Chat
            const chatItem = new PopupMenu.PopupMenuItem('Open Chat');
            chatItem.connect('activate', () => {
                console.log(`[ShareBridge] Opening chat with ${peerData.name}`);
                // Step 8 logic will go here
            });
            peerSubMenu.menu.addMenuItem(chatItem);

            // Action: Share Screen
            const screenShareItem = new PopupMenu.PopupMenuItem('Share Screen');
            screenShareItem.connect('activate', () => {
                console.log(`[ShareBridge] Starting screen share with ${peerData.name}`);
                // Step 9 logic will go here
            });
            peerSubMenu.menu.addMenuItem(screenShareItem);

            // Mount to the DOM equivalent and save to state
            this._peerSection.addMenuItem(peerSubMenu);
            this._peers.set(peerData.id, peerSubMenu);
        }

        /**
         * Cleans up the UI node when a peer drops off the network
         * @param {string} peerId 
         */
        removePeer(peerId) {
            const peerItem = this._peers.get(peerId);
            if (peerItem) {
                peerItem.destroy(); // Properly unmounts the Clutter actor
                this._peers.delete(peerId);
            }

            // Restore placeholder if network is empty
            if (this._peers.size === 0 && !this._noPeersItem) {
                this._noPeersItem = new PopupMenu.PopupMenuItem('Scanning local network...', { reactive: false });
                this._peerSection.addMenuItem(this._noPeersItem);
            }
        }

        destroy() {
            this._peers.clear();
            super.destroy();
        }
    }
);