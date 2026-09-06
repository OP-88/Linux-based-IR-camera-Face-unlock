#!/bin/bash

# Ensure we are in a virtual environment for a clean build
if [ ! -d "venv" ]; then
    echo "Creating isolated build environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing build dependencies..."
pip install pyinstaller opencv-python-headless numpy cryptography

echo "Compiling FaceLock into a standalone binary..."
pyinstaller --onefile --name facelock \
    --add-data "models/yunet.onnx:models" \
    --add-data "models/sface.onnx:models" \
    --hidden-import="cv2" \
    --hidden-import="numpy" \
    --hidden-import="cryptography" \
    src/facelock.py

echo "Build complete! Your standalone air-gapped binary is located at:"
echo "dist/facelock"

echo "To install system-wide, simply move it:"
echo "sudo cp dist/facelock /usr/local/bin/facelock"
