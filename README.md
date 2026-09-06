# Linux IR Camera Face Unlock

A highly secure, zero-knowledge biometric authentication engine for Linux, utilizing Infrared (IR) cameras.

## Security Model (Zero-Knowledge Vault)
Instead of storing pictures of your face, this tool extracts a 128-dimensional mathematical representation of your facial geometry using OpenCV's AI models (YuNet & SFace). 

To prevent Model Inversion attacks (reconstructing an image from the data points), the vector is **quantized**.
Finally, the data is encrypted via AES-256 using a hardware-bound key generated from your `/etc/machine-id`. If someone steals your biometric vault file, it is mathematically irreversible and useless on another machine.

## Setup

1. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Enroll your face:
```bash
python src/enroll.py
```
*(Looks for a camera at `/dev/video2`. The script will download the required ONNX AI models on first run).*

3. Test Authentication:
```bash
python src/auth.py
```

## PAM Integration
*Coming soon: Instructions for wrapping this into a PAM module for `sudo` and lockscreen auth.*
