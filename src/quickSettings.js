// src/quickSettings.js
import GObject from 'gi://GObject';
import * as QuickSettings from 'resource:///org/gnome/shell/ui/quickSettings.js';

/**
 * The actual pill-shaped toggle button in the Quick Settings grid.
 */
const ShareBridgeToggle = GObject.registerClass(
    class ShareBridgeToggle extends QuickSettings.QuickToggle {
        _init() {
            super._init({
                title: 'ShareBridge',
                subtitle: 'Scanning local network...',
                iconName: 'network-transmit-receive-symbolic',
                toggleMode: true,
            });

            // Default state is active when the extension starts
            this.checked = true;

            // Listen for the user clicking the toggle
            this.connect('clicked', () => this._onToggleClicked());
        }

        _onToggleClicked() {
            if (this.checked) {
                this.subtitle = 'Active';
                console.log('[ShareBridge] Quick Toggle: Resumed network discovery');
                // In a future step, we'll emit a D-Bus call to tell Python to resume mDNS
            } else {
                this.subtitle = 'Paused';
                console.log('[ShareBridge] Quick Toggle: Paused network discovery');
                // In a future step, we'll emit a D-Bus call to tell Python to stop mDNS
            }
        }

        /**
         * Updates the subtitle text based on current peer count.
         * @param {number} count 
         */
        updatePeerCount(count) {
            if (!this.checked) return; // Don't update text if we are manually paused
            
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

/**
 * The system indicator container that GNOME expects us to inject.
 */
export const ShareBridgeIndicator = GObject.registerClass(
    class ShareBridgeIndicator extends QuickSettings.SystemIndicator {
        _init() {
            super._init();
            
            // Create our toggle and add it to the container's item list
            this._toggle = new ShareBridgeToggle();
            this.quickSettingsItems.push(this._toggle);
        }

        // Expose the toggle so extension.js can send it peer count updates
        get toggle() {
            return this._toggle;
        }
    }
);