// prefs.js
import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import { ExtensionPreferences } from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class ShareBridgePreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({ title: 'General Settings' });

        const downloadDirRow = new Adw.ActionRow({
            title: 'Download Directory',
            subtitle: 'Where received files will be saved'
        });

        // Use a text entry to let the user type or paste the path
        const entry = new Adw.EntryRow({ 
            title: 'Absolute Path',
            text: settings.get_string('download-dir') || GLib.get_home_dir() + '/Downloads'
        });

        // Bind the text entry directly to the GSchema key
        settings.bind('download-dir', entry, 'text', Gio.SettingsBindFlags.DEFAULT);

        group.add(downloadDirRow);
        group.add(entry);
        page.add(group);
        window.add(page);
    }
}