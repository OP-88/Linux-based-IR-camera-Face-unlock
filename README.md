# Linux IR Camera Face Unlock

A highly secure, zero-knowledge biometric authentication engine for Linux, utilizing Infrared (IR) cameras. 

## Features
- **Air-Gapped:** Uses bundled AI models. Connects to zero networks.
- **Standalone:** Packaged into a single Linux executable via PyInstaller.
- **Zero-Knowledge Security:** Converts facial geometry into a mathematically irreversible 128-d quantized vector.
- **Hardware Bound:** Encrypts your face vault using a key derived from your motherboard's `/etc/machine-id`.
- **Automated Injection:** Safely edits Linux PAM configuration files with a single click.

## Installation

You can run the application immediately without installing Python or dependencies.

1. Clone this repository and compile the app:
```bash
git clone https://github.com/OP-88/Linux-based-IR-camera-Face-unlock.git
cd Linux-based-IR-camera-Face-unlock
chmod +x build.sh
./build.sh
```

2. Move the compiled binary into your system path:
```bash
sudo cp dist/facelock /usr/local/bin/facelock
```

## Usage (GUI)

The application now ships with a fully graphical interface! Just run:
```bash
facelock gui
```
From here you can enroll your face, test the camera, and enable or disable the system-wide lock integration with a single click.

## Usage (CLI)

If you prefer the terminal:
- Enroll your face: `sudo facelock enroll`
- Test your camera: `sudo facelock test`
- Inject into Linux login/sudo screens: `sudo facelock install-pam`
- Remove from Linux login/sudo screens: `sudo facelock uninstall-pam`
