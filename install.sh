#!/bin/bash

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo ./install.sh"
  exit 1
fi

echo "Setting up FaceLock directories..."
mkdir -p /etc/facelock
mkdir -p /var/lib/facelock
mkdir -p /usr/share/facelock/models
mkdir -p /opt/facelock

# Secure the vault directory
chmod 700 /var/lib/facelock

echo "Downloading AI Models to global storage..."
curl -sL -o /usr/share/facelock/models/yunet.onnx "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
curl -sL -o /usr/share/facelock/models/sface.onnx "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

echo "Setting up secure Python Virtual Environment..."
python3 -m venv /opt/facelock/venv
/opt/facelock/venv/bin/pip install opencv-python-headless numpy cryptography

echo "Copying CLI tool..."
cp src/facelock.py /opt/facelock/facelock.py
chmod +x /opt/facelock/facelock.py

echo "Creating executable wrapper..."
rm -f /usr/local/bin/facelock
cat << 'EOF' > /usr/local/bin/facelock
#!/bin/bash
exec /opt/facelock/venv/bin/python /opt/facelock/facelock.py "$@"
EOF
chmod +x /usr/local/bin/facelock

echo "Setting up default configuration..."
if [ ! -f /etc/facelock/config.ini ]; then
    cat <<EOF > /etc/facelock/config.ini
[camera]
# The path to your IR camera. You can test which one it is using 'v4l2-ctl --list-devices'
device_path = /dev/video2
# How long (in seconds) the system should look for your face before falling back to a password
timeout = 5.0

[security]
# OpenCV SFace threshold. 0.363 is the mathematically proven cutoff for a match.
threshold = 0.363
EOF
fi

echo ""
echo "Installation complete!"
echo "----------------------"
echo "To enroll your face:  sudo facelock enroll"
echo "To test your camera:  facelock test"
echo "To change camera:     sudo facelock config"
echo ""
echo "Note: This script installed the tool but did NOT modify your PAM configuration yet."
echo "To use this for 'sudo', you must add the following line to the top of /etc/pam.d/sudo:"
echo "    auth sufficient pam_exec.so stdout /usr/local/bin/facelock auth-pam"
