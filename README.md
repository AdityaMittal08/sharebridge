# ShareBridge

**ShareBridge** is a secure P2P collaboration suite and GNOME Shell extension that brings native, zero-configuration LAN file transfers and WebRTC screen sharing directly to your desktop.

Developed by Aditya Mittal, this extension bridges the gap between devices on your local network using mDNS discovery, Python-powered D-Bus daemons, and PipeWire for secure screen broadcasting. It is heavily optimized and tested for Ubuntu and other modern GNOME environments.

##  Key Features
* **Zero-Config Discovery:** Automatically finds other devices on your local network using mDNS. Toggling the extension off instantly removes your device from the network.
* **Secure LAN File Transfer:** Send files peer-to-peer with SHA-256 integrity checks. Features a strict TCP handshake that explicitly waits for receiver consent before streaming data.
* **Wayland Screen Sharing:** Secure, high-definition screen broadcasting leveraging PipeWire and WebRTC. Includes explicit native prompts to prevent unsolicited screen casting.
* **Native GNOME Integration:** Accessible directly from your top panel and Quick Settings.

---

##  Prerequisites

Before installing, ensure your system has the required native dependencies. We utilize your system's pre-compiled GObject Introspection bindings for maximum stability. 

If you are using Ubuntu/Debian, run the following command in your terminal:

```bash
sudo apt update
sudo apt install python3-venv python3-pip python3-gi python3-gi-cairo zenity gir1.2-gst-plugins-bad-1.0 gstreamer1.0-plugins-bad gstreamer1.0-nice
```


**Installation**
Clone this repository and run the automated install script. This script will package the extension, place it in your local GNOME extensions directory, compile the schemas, and build the required Python virtual environment safely linked to your system packages.


```Bash
git clone [https://github.com/AdityaMittal08/sharebridge.git](https://github.com/AdityaMittal08/sharebridge.git)
cd sharebridge
chmod +x install.sh
./install.sh
```

**Activation**
Restart GNOME Shell:

* Wayland: Log out of your user session and log back in.

* X11: Press Alt + F2, type r, and press Enter.

Enable the Extension: Open the Extensions app and toggle ShareBridge on, or run this command:

```bash
gnome-extensions enable sharebridge@adishare.com
```


**Configuration**
By default, files are downloaded to ~/Downloads/ShareBridge. You can change the download directory by opening the GNOME Extensions app, clicking the gear icon next to ShareBridge, and specifying a new absolute path.


**Contributing**
Contributions, issues, and feature requests are welcome! Feel free to check the issues page if you want to contribute to this open-source project.

