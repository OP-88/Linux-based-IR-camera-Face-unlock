#!/bin/bash

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo ./install.sh"
  exit 1
fi

echo "Setting up Infra Lock directories..."
mkdir -p /etc/infralock
mkdir -p /var/lib/infralock
mkdir -p /usr/share/infralock/models
mkdir -p /opt/infralock

# Secure the vault directory but allow users to read their own vaults
chmod 755 /var/lib/infralock

echo "Downloading AI Models to global storage..."
curl -sL -o /usr/share/infralock/models/yunet.onnx "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
curl -sL -o /usr/share/infralock/models/sface.onnx "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

echo "Setting up secure Python Virtual Environment..."
python3 -m venv /opt/infralock/venv
/opt/infralock/venv/bin/pip install opencv-python-headless numpy cryptography

echo "Copying CLI tool..."
cp src/infralock.py /opt/infralock/infralock.py
chmod +x /opt/infralock/infralock.py

echo "Creating executable wrapper..."
rm -f /usr/local/bin/infralock
cat << 'EOF' > /usr/local/bin/infralock
#!/bin/bash
exec /opt/infralock/venv/bin/python /opt/infralock/infralock.py "$@"
EOF
chmod +x /usr/local/bin/infralock

echo "Setting up default configuration..."
if [ ! -f /etc/infralock/config.ini ]; then
    cat <<EOF > /etc/infralock/config.ini
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
echo "To enroll your face:  sudo infralock enroll"
echo "To test your camera:  infralock test"
echo "To change camera:     sudo infralock config"
echo ""
echo "Note: This script installed the tool but did NOT modify your PAM configuration yet."
echo "To use this for 'sudo', you must add the following line to the top of /etc/pam.d/sudo:"
echo "    auth sufficient pam_exec.so stdout /usr/local/bin/infralock auth-pam"
