#!/bin/bash
echo "Installing ShareBridge dependencies..."
cd ~/.local/share/gnome-shell/extensions/sharebridge@adishare.com/daemon

# Create a virtual environment
python3 -m venv venv

# Activate it and install requirements
source venv/bin/activate
pip install -r requirements.txt

echo "Installation complete. Please restart GNOME Shell (Alt+F2, type 'r', Enter) or log out and log back in."