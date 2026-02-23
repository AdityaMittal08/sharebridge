// src/panel.js
import GObject from 'gi://GObject';
import St from 'gi://St';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import { pickFile } from './fileTransfer.js';

export const ShareBridgePanel = GObject.registerClass({
    Signals: {
        'file-send-requested': { param_types: [GObject.TYPE_STRING, GObject.TYPE_STRING] },
        'chat-requested': { param_types: [GObject.TYPE_STRING, GObject.TYPE_STRING] },
        'screen-share-requested': { param_types: [GObject.TYPE_STRING] },
        'screen-share-stop-requested': { param_types: [] }
    }
}, class ShareBridgePanel extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'ShareBridge Indicator');
        this._icon = new St.Icon({
            icon_name: 'network-transmit-receive-symbolic',
            style_class: 'system-status-icon',
        });
        this.add_child(this._icon);
        this._peers = new Map();
        this._buildMenu();
    }

    _buildMenu() {
        this._headerItem = new PopupMenu.PopupMenuItem('ShareBridge', { reactive: false });
        this._headerItem.label.get_clutter_text().set_markup('<b>ShareBridge</b>');
        this.menu.addMenuItem(this._headerItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._peerSection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._peerSection);
        this._noPeersItem = new PopupMenu.PopupMenuItem('Scanning local network...', { reactive: false });
        this._peerSection.addMenuItem(this._noPeersItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._settingsItem = new PopupMenu.PopupMenuItem('Preferences');
        this.menu.addMenuItem(this._settingsItem);
    }

    addPeer(peerData) {
        if (this._noPeersItem) {
            this._noPeersItem.destroy();
            this._noPeersItem = null;
        }
        if (this._peers.has(peerData.id)) return;

        const peerSubMenu = new PopupMenu.PopupSubMenuMenuItem(peerData.name);

        const sendFileItem = new PopupMenu.PopupMenuItem('Send File...');
        sendFileItem.connect('activate', async () => {
            const filePath = await pickFile();
            if (filePath) this.emit('file-send-requested', peerData.id, filePath);
        });
        peerSubMenu.menu.addMenuItem(sendFileItem);

        const chatItem = new PopupMenu.PopupMenuItem('Open Chat');
        chatItem.connect('activate', () => {
            this.menu.close();
            this.emit('chat-requested', peerData.id, peerData.name);
        });
        peerSubMenu.menu.addMenuItem(chatItem);

        const screenShareItem = new PopupMenu.PopupMenuItem('Share Screen');
        screenShareItem.connect('activate', () => {
            this.menu.close();
            this.emit('screen-share-requested', peerData.id);
        });
        peerSubMenu.menu.addMenuItem(screenShareItem);

        const stopShareItem = new PopupMenu.PopupMenuItem('Stop Screen Share');
        stopShareItem.connect('activate', () => {
            this.menu.close();
            this.emit('screen-share-stop-requested');
        });
        peerSubMenu.menu.addMenuItem(stopShareItem);

        this._peerSection.addMenuItem(peerSubMenu);
        this._peers.set(peerData.id, peerSubMenu);
    }

    removePeer(peerId) {
        const peerItem = this._peers.get(peerId);
        if (peerItem) {
            peerItem.destroy();
            this._peers.delete(peerId);
        }
        if (this._peers.size === 0 && !this._noPeersItem) {
            this._noPeersItem = new PopupMenu.PopupMenuItem('Scanning local network...', { reactive: false });
            this._peerSection.addMenuItem(this._noPeersItem);
        }
    }

    destroy() {
        this._peers.clear();
        super.destroy();
    }
});