#!/bin/bash
# install.sh

# Get the absolute path of the extension directory
EXTENSION_DIR=$(cd "$(dirname "$0")" && pwd)
DAEMON_DIR="$EXTENSION_DIR/daemon"

echo "Installing ShareBridge dependencies in $EXTENSION_DIR..."

# 1. Compile the GSettings schemas
if [ -d "$EXTENSION_DIR/schemas" ]; then
    echo "Compiling schemas..."
    glib-compile-schemas "$EXTENSION_DIR/schemas/"
else
    echo "Error: schemas directory not found."
    exit 1
fi

# 2. Setup Python Virtual Environment
cd "$DAEMON_DIR"
python3 -m venv venv

# 3. Install requirements
source venv/bin/activate
pip install -r requirements.txt

echo "-------------------------------------------------------"
echo "Installation complete."
echo "To test manually, run these commands in your terminal:"
echo "  source $DAEMON_DIR/venv/bin/activate"
echo "  export XDG_DATA_DIRS=\$XDG_DATA_DIRS:$EXTENSION_DIR"
echo "  python3 $DAEMON_DIR/sharebridge-daemon.py"
echo "-------------------------------------------------------"
echo "Please restart GNOME Shell to activate the extension UI."