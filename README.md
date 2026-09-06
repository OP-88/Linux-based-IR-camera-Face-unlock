# Linux IR Camera Face Unlock

A highly secure, zero-knowledge biometric authentication engine for Linux, utilizing Infrared (IR) cameras.

## Security Model (Zero-Knowledge Vault)
Instead of storing pictures of your face, this tool extracts a 128-dimensional mathematical representation of your facial geometry using OpenCV's AI models (YuNet & SFace). 

To prevent Model Inversion attacks (reconstructing an image from the data points), the vector is **quantized**.
Finally, the data is encrypted via AES-256 using a hardware-bound key generated from your `/etc/machine-id`. If someone steals your biometric vault file, it is mathematically irreversible and useless on another machine.

## Setup

1. Run the installer to create the virtual environment and system endpoints:
```bash
sudo ./install.sh
```

2. Enroll your face (will use `/dev/video2` by default):
```bash
sudo facelock enroll
```

3. Test Authentication (Dry-run without locking your system):
```bash
sudo facelock test
```

## PAM Integration
To use this to bypass passwords for `sudo`, add the following line to the top of `/etc/pam.d/sudo`:
```text
auth sufficient pam_exec.so stdout seteuid /usr/local/bin/facelock auth-pam
```
