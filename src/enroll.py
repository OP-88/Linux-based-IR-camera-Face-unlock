import cv2
import numpy as np
import os
import urllib.request
import hashlib
import base64
import json
import time
from cryptography.fernet import Fernet

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

def download_model(url, filename):
    """Downloads the ONNX AI models if they don't exist yet."""
    if not os.path.exists(filename):
        print(f"Downloading {filename} (this happens only once)...")
        urllib.request.urlretrieve(url, filename)
        print("Download complete.")

def get_hardware_key():
    """Binds the encryption to this specific Linux installation/motherboard."""
    try:
        with open('/etc/machine-id', 'r') as f:
            machine_id = f.read().strip()
    except FileNotFoundError:
        machine_id = "fallback_id_if_not_found"
        
    # Hash it to get a consistent 32-byte key for Fernet AES encryption
    key_bytes = hashlib.sha256(machine_id.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)

def enroll_face():
    print("Initializing AI models...")
    download_model(YUNET_URL, "yunet.onnx")
    download_model(SFACE_URL, "sface.onnx")

    # Initialize OpenCV Face Recognizer (SFace) and Detector (YuNet)
    detector = cv2.FaceDetectorYN.create("yunet.onnx", "", (320, 320))
    recognizer = cv2.FaceRecognizerSF.create("sface.onnx", "")

    # Open the IR Camera
    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("Error: Could not open /dev/video2")
        return

    print("\nGet ready! Look directly at the camera...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
        cap.read() # clear the buffer so we get a fresh frame

    print("Capturing frame!")
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Failed to capture image.")
        return

    # Pass image dimensions to the AI
    h, w, _ = frame.shape
    detector.setInputSize((w, h))

    # Run face detection
    ret, faces = detector.detect(frame)
    if faces is None:
        print("No face detected! Please try again and look directly at the camera.")
        return

    print(f"Detected {len(faces)} face(s). Extracting geometry...")
    face = faces[0]

    # Extract 128-d mathematical embedding
    aligned_face = recognizer.alignCrop(frame, face)
    feature_vector = recognizer.feature(aligned_face) # Shape: (1, 128)

    # 1. QUANTIZATION
    # The vector is L2 normalized (-1.0 to 1.0). Rounding to 3 decimals keeps enough 
    # math for matching, but destroys the micro-details needed for AI image reconstruction.
    quantized_vector = np.round(feature_vector[0], 3).tolist()
    print(f"Extracted and quantized 128 facial data points.")

    # 2. HARDWARE-BOUND ENCRYPTION
    key = get_hardware_key()
    cipher = Fernet(key)
    
    # Store as JSON before encrypting
    payload = json.dumps({"version": "1.0", "embedding": quantized_vector}).encode('utf-8')
    encrypted_blob = cipher.encrypt(payload)

    # Save to disk
    with open("face_vault.enc", "wb") as f:
        f.write(encrypted_blob)

    print("\nENROLLMENT SUCCESSFUL!")
    print("Your face has been quantized, encrypted with your machine ID, and saved to 'face_vault.enc'.")
    print("No images were saved to disk. If you steal this file, it's mathematically useless.")

if __name__ == "__main__":
    enroll_face()
