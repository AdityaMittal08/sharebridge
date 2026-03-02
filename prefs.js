import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import { ExtensionPreferences } from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class ShareBridgePreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({ title: 'General Settings' });

        const downloadDirRow = new Adw.ActionRow({
            title: 'Download Directory',
            subtitle: 'Where received files will be saved'
        });

        // Add a button to open a folder picker (simplified for example)
        const btn = new Gio.Settings({ schema_id: this.metadata['settings-schema'] });
        
        group.add(downloadDirRow);
        page.add(group);
        window.add(page);
    }
}