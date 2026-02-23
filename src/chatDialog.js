// src/chatDialog.js
import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import { ModalDialog } from 'resource:///org/gnome/shell/ui/modalDialog.js';

export const ChatDialog = GObject.registerClass(
class ChatDialog extends ModalDialog {
    _init(peerId, peerName, daemonProxy) {
        super._init({ styleClass: 'prompt-dialog' });
        
        this.peerId = peerId;
        this.peerName = peerName;
        this.daemonProxy = daemonProxy;

        this._buildUI();
        this._loadHistory();
    }

    _buildUI() {
        // 1. Header
        const title = new St.Label({
            text: `Chat with ${this.peerName}`,
            style_class: 'prompt-dialog-headline'
        });
        this.contentLayout.add_child(title);

        // 2. Message History Area (Scrollable)
        this.scrollView = new St.ScrollView({
            style_class: 'vfade',
            x_expand: true,
            y_expand: true,
            hscrollbar_policy: St.PolicyType.NEVER,
            vscrollbar_policy: St.PolicyType.AUTOMATIC,
        });
        // Hardcode a reasonable size for the chat box
        this.scrollView.set_size(400, 300);

        this.messageBox = new St.BoxLayout({
            vertical: true,
            x_expand: true,
            y_expand: true,
            style: 'padding: 10px; spacing: 8px;'
        });
        this.scrollView.add_child(this.messageBox);
        this.contentLayout.add_child(this.scrollView);

        // 3. Text Input Field
        this.inputEntry = new St.Entry({
            hint_text: 'Type a message...',
            style: 'margin-top: 15px; padding: 8px; border-radius: 8px;',
            can_focus: true,
            x_expand: true
        });
        
        // Listen for the "Enter" key
        this.inputEntry.clutter_text.connect('activate', this._sendMessage.bind(this));
        this.contentLayout.add_child(this.inputEntry);

        // 4. Action Buttons
        this.setButtons([
            {
                label: 'Close',
                action: this.close.bind(this),
                key: Clutter.KEY_Escape
            },
            {
                label: 'Send',
                action: this._sendMessage.bind(this),
                default: true
            }
        ]);
    }

    _loadHistory() {
        // Fetch history from Python's SQLite database
        this.daemonProxy.GetChatHistoryRemote(this.peerId, (result, error) => {
            if (error) {
                console.error(`[ShareBridge] Failed to load history: ${error.message}`);
                return;
            }
            if (result && result[0]) {
                const history = JSON.parse(result[0]);
                history.forEach(msg => {
                    this.addMessage(msg.is_outgoing, msg.content);
                });
                this._scrollToBottom();
            }
        });
    }

    _sendMessage() {
        const text = this.inputEntry.get_text().trim();
        if (!text) return;

        // Clear input field immediately
        this.inputEntry.set_text('');

        // Send to Python daemon over D-Bus
        this.daemonProxy.SendMessageRemote(this.peerId, text, (result, error) => {
            if (error || (result && result[0] === false)) {
                console.error(`[ShareBridge] Failed to send message.`);
                this.addMessage(true, `[Failed] ${text}`);
            } else {
                this.addMessage(true, text);
            }
            this._scrollToBottom();
        });
    }

    addMessage(isOutgoing, text) {
        // Simple styling to differentiate sent vs received messages
        const align = isOutgoing ? Clutter.ActorAlign.END : Clutter.ActorAlign.START;
        const bgColor = isOutgoing ? 'background-color: #3584e4; color: white;' : 'background-color: #3d3d3d; color: white;';
        
        const bubble = new St.Label({
            text: text,
            x_align: align,
            style: `padding: 8px 12px; border-radius: 12px; max-width: 300px; ${bgColor}`
        });
        
        // Ensure text wraps if it's too long
        bubble.clutter_text.line_wrap = true;
        bubble.clutter_text.line_wrap_mode = 0; // Pango.WrapMode.WORD

        const wrapper = new St.BoxLayout({
            x_expand: true,
            x_align: align
        });
        wrapper.add_child(bubble);

        this.messageBox.add_child(wrapper);
        this._scrollToBottom();
    }

    _scrollToBottom() {
        // Small delay to allow the UI layout to calculate the new height before scrolling
        import('gi://GLib').then(GLib => {
            GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
                const adjustment = this.scrollView.vscroll.adjustment;
                adjustment.value = adjustment.upper - adjustment.page_size;
                return GLib.SOURCE_REMOVE;
            });
        });
    }
});