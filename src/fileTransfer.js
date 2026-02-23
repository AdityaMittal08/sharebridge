// src/fileTransfer.js
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

/**
 * Opens a native file picker dialog and returns the selected file path.
 * Uses Zenity via a subprocess to avoid GTK window parent context issues in GNOME Shell.
 * @returns {Promise<string|null>} The file path, or null if canceled.
 */
export async function pickFile() {
    return new Promise((resolve, reject) => {
        try {
            // Launch zenity file selection dialog
            let proc = Gio.Subprocess.new(
                ['zenity', '--file-selection', '--title=Select File to Send via ShareBridge'],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );

            proc.communicate_utf8_async(null, null, (proc, res) => {
                try {
                    let [ok, stdout, stderr] = proc.communicate_utf8_finish(res);
                    if (proc.get_successful()) {
                        // Zenity returns the path with a trailing newline
                        resolve(stdout.trim());
                    } else {
                        // User canceled the dialog
                        resolve(null);
                    }
                } catch (e) {
                    console.error(`[ShareBridge] File picker error: ${e.message}`);
                    resolve(null);
                }
            });
        } catch (e) {
            console.error(`[ShareBridge] Failed to launch file picker: ${e.message}`);
            resolve(null);
        }
    });
}