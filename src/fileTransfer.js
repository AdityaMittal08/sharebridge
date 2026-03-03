// src/fileTransfer.js
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

/**
 * Opens a native file picker dialog and returns the selected file path.
 * Uses Zenity via a subprocess to avoid GTK window parent context issues in GNOME Shell.
 * @returns {Promise<string|null>} The file path, or null if canceled.
 */
export async function pickFile() {
    return new Promise((resolve, reject) => {
        try {
            let proc = Gio.Subprocess.new(
                ['zenity', '--file-selection', '--title=Select File to Send via ShareBridge'],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );

            proc.communicate_utf8_async(null, null, (proc, res) => {
                try {
                    let [ok, stdout, stderr] = proc.communicate_utf8_finish(res);
                    if (proc.get_successful()) {
                        resolve(stdout.trim());
                    } else {
                        resolve(null);
                    }
                } catch (e) {
                    console.error(`[ShareBridge] File picker error: ${e.message}`);
                    resolve(null);
                }
            });
        } catch (e) {
            console.error(`[ShareBridge] Failed to launch file picker (Is zenity installed?): ${e.message}`);
            Main.notify('ShareBridge Error', 'Failed to launch file picker. Please ensure "zenity" is installed.');
            resolve(null);
        }
    });
}