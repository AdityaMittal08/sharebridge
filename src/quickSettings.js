// src/quickSettings.js
import GObject from 'gi://GObject';
import * as QuickSettings from 'resource:///org/gnome/shell/ui/quickSettings.js';

const ShareBridgeToggle = GObject.registerClass(
    class ShareBridgeToggle extends QuickSettings.QuickToggle {
        _init() {
            super._init({
                title: 'ShareBridge',
                subtitle: 'Scanning local network...',
                iconName: 'network-transmit-receive-symbolic',
                toggleMode: true,
            });

            this.checked = true;
            this._daemonProxy = null;

            this.connect('clicked', () => this._onToggleClicked());
        }

        setDaemonProxy(proxy) {
            this._daemonProxy = proxy;
        }

        _onToggleClicked() {
            if (this.checked) {
                this.subtitle = 'Active';
                console.log('[ShareBridge] Quick Toggle: Resumed network discovery');
                if (this._daemonProxy) this._daemonProxy.ResumeDiscoveryRemote((result, err) => {
                    if (err) console.error(`[ShareBridge] Failed to resume: ${err.message}`);
                });
            } else {
                this.subtitle = 'Paused';
                console.log('[ShareBridge] Quick Toggle: Paused network discovery');
                if (this._daemonProxy) this._daemonProxy.PauseDiscoveryRemote((result, err) => {
                     if (err) console.error(`[ShareBridge] Failed to pause: ${err.message}`);
                });
            }
        }

        updatePeerCount(count) {
            if (!this.checked) return; 
            
            if (count === 0) {
                this.subtitle = 'No peers found';
            } else if (count === 1) {
                this.subtitle = '1 peer connected';
            } else {
                this.subtitle = `${count} peers connected`;
            }
        }
    }
);

export const ShareBridgeIndicator = GObject.registerClass(
    class ShareBridgeIndicator extends QuickSettings.SystemIndicator {
        _init() {
            super._init();
            
            this._toggle = new ShareBridgeToggle();
            this.quickSettingsItems.push(this._toggle);
        }

        get toggle() {
            return this._toggle;
        }
    }
);