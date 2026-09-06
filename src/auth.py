import cv2
import numpy as np
import hashlib
import base64
import json
import sys
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

# OpenCV's official SFace threshold for Cosine Similarity is 0.363.
# A score >= 0.363 means it's a mathematically proven match.
THRESHOLD = 0.363

def get_hardware_key():
    """Reads the machine ID to derive the exact same decryption key."""
    try:
        with open('/etc/machine-id', 'r') as f:
            machine_id = f.read().strip()
    except FileNotFoundError:
        machine_id = "fallback_id_if_not_found"
    key_bytes = hashlib.sha256(machine_id.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)

def load_vault():
    """Decrypts the vault file safely."""
    try:
        with open("face_vault.enc", "rb") as f:
            encrypted_blob = f.read()
        
        cipher = Fernet(get_hardware_key())
        decrypted_payload = cipher.decrypt(encrypted_blob)
        data = json.loads(decrypted_payload)
        
        print("Vault successfully decrypted using local hardware key.")
        return np.array(data["embedding"], dtype=np.float32)
        
    except InvalidToken:
        print("SECURITY LOCKOUT: Cannot decrypt vault. Incorrect hardware key!")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: face_vault.enc not found. Please run enroll.py first.")
        sys.exit(1)

def authenticate():
    print("Initiating Authentication Sequence...\n")
    stored_embedding = load_vault()

    # Load AI in silent mode
    detector = cv2.FaceDetectorYN.create("yunet.onnx", "", (320, 320))
    recognizer = cv2.FaceRecognizerSF.create("sface.onnx", "")

    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("Error: Could not open IR Camera.")
        sys.exit(1)

    print("Scanning face... (Looking for you...)")
    
    import time
    start_time = time.time()
    face_found = False
    frame = None
    face = None
    
    # Loop for up to 5 seconds waiting for the camera to warm up and find a face
    while time.time() - start_time < 5.0:
        ret, current_frame = cap.read()
        if not ret:
            continue
            
        h, w, _ = current_frame.shape
        detector.setInputSize((w, h))
        
        ret, faces = detector.detect(current_frame)
        if faces is not None and len(faces) > 0:
            face_found = True
            frame = current_frame
            face = faces[0]
            break
            
    cap.release()

    if not face_found:
        print("Authentication Failed: No face detected within 5 seconds.")
        sys.exit(1)

    print("Face detected! Verifying identity...")
    aligned_face = recognizer.alignCrop(frame, face)
    feature_vector = recognizer.feature(aligned_face)

    # 1. Quantize the LIVE vector exactly how we quantized the stored one
    live_embedding = np.round(feature_vector[0], 3).astype(np.float32)

    # 2. Compare the two vectors using Cosine Similarity
    score = recognizer.match(
        stored_embedding.reshape(1, 128),
        live_embedding.reshape(1, 128),
        cv2.FaceRecognizerSF_FR_COSINE
    )

    print("\n--- MATCH RESULTS ---")
    print(f"Similarity Score: {score:.4f} (Required: >= {THRESHOLD})")
    
    if score >= THRESHOLD:
        print("\nACCESS GRANTED! Welcome back.")
        sys.exit(0)
    else:
        print("\nACCESS DENIED! Face does not match vault.")
        sys.exit(1)

if __name__ == "__main__":
    authenticate()
