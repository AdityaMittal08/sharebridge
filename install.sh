#!/bin/bash
# install.sh

UUID="sharebridge@adishare.com"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$UUID"
REPO_DIR=$(cd "$(dirname "$0")" && pwd)

echo "======================================================="
echo " Installing ShareBridge Extension"
echo "======================================================="

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 could not be found. Please install it."
    exit 1
fi

if ! command -v glib-compile-schemas &> /dev/null; then
    echo "Error: glib-compile-schemas not found. Please install libglib2.0-bin."
    exit 1
fi

echo "[1/4] Preparing extension directory..."
rm -rf "$EXT_DIR"
mkdir -p "$EXT_DIR"

echo "[2/4] Copying files to $EXT_DIR..."
cp -r "$REPO_DIR/daemon" "$EXT_DIR/"
cp -r "$REPO_DIR/schemas" "$EXT_DIR/"
cp -r "$REPO_DIR/src" "$EXT_DIR/"
cp "$REPO_DIR/extension.js" "$EXT_DIR/"
cp "$REPO_DIR/metadata.json" "$EXT_DIR/"
cp "$REPO_DIR/prefs.js" "$EXT_DIR/"
cp "$REPO_DIR/stylesheet.css" "$EXT_DIR/"

echo "[3/4] Compiling GSettings schemas..."
glib-compile-schemas "$EXT_DIR/schemas/"

echo "[4/4] Setting up Python virtual environment (this may take a moment)..."
cd "$EXT_DIR/daemon"
python3 -m venv venv

source venv/bin/activate
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
pip install -r requirements.txt
deactivate

echo "======================================================="
echo " Installation Complete!"
echo "======================================================="
echo ""
echo "To activate ShareBridge, please follow these steps:"
echo "  1. Restart GNOME Shell:"
echo "     - On Wayland: Log out and log back in."
echo "     - On X11: Press Alt+F2, type 'r', and press Enter."
echo "  2. Enable the extension using the GNOME Extensions app,"
echo "     or by running the following command:"
echo ""
echo "     gnome-extensions enable $UUID"
echo ""
echo "======================================================="