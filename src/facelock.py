#!/usr/bin/env python3
import cv2
import numpy as np
import hashlib
import base64
import json
import sys
import os
import time
import argparse
import configparser
import syslog
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

# System Paths
CONFIG_FILE = "/etc/facelock/config.ini"
VAULT_DIR = "/var/lib/facelock"
MODELS_DIR = "/usr/share/facelock/models"

def load_config():
    config = configparser.ConfigParser()
    # Defaults
    config.read_dict({
        'camera': {'device_path': '/dev/video2', 'timeout': '5.0'},
        'security': {'threshold': '0.363'}
    })
    config.read(CONFIG_FILE)
    return config

def log_auth(message, level=syslog.LOG_INFO):
    """Log to /var/log/auth.log"""
    syslog.openlog(ident="facelock", facility=syslog.LOG_AUTH)
    syslog.syslog(level, message)
    syslog.closelog()

def get_hardware_key():
    try:
        with open('/etc/machine-id', 'r') as f:
            machine_id = f.read().strip()
    except FileNotFoundError:
        machine_id = "fallback_id_if_not_found"
    key_bytes = hashlib.sha256(machine_id.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)

def init_ai_models():
    yunet_path = os.path.join(MODELS_DIR, "yunet.onnx")
    sface_path = os.path.join(MODELS_DIR, "sface.onnx")
    
    if not os.path.exists(yunet_path) or not os.path.exists(sface_path):
        print(f"Error: AI models not found in {MODELS_DIR}. Run install.sh first.")
        sys.exit(1)
        
    detector = cv2.FaceDetectorYN.create(yunet_path, "", (320, 320))
    recognizer = cv2.FaceRecognizerSF.create(sface_path, "")
    return detector, recognizer

def scan_face(cap, detector, timeout=5.0):
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        ret, frame = cap.read()
        if not ret:
            continue
            
        # Some cameras (or GStreamer backends) return 1-channel grayscale. 
        # YuNet expects 3-channel BGR.
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            
        h, w, _ = frame.shape
        
        # YuNet crashes if dimensions aren't multiples of 32 (tensor mismatch)
        new_h = int(np.ceil(h / 32.0) * 32)
        new_w = int(np.ceil(w / 32.0) * 32)
        
        if new_h != h or new_w != w:
            pad_frame = np.zeros((new_h, new_w, 3), dtype=np.uint8)
            pad_frame[:h, :w, :] = frame
            detector.setInputSize((new_w, new_h))
            ret, faces = detector.detect(pad_frame)
        else:
            detector.setInputSize((w, h))
            ret, faces = detector.detect(frame)
            
        if faces is not None and len(faces) > 0:
            return frame, faces[0]
            
    return None, None

def enroll(username, config):
    print(f"Enrolling face for user: {username}")
    detector, recognizer = init_ai_models()
    
    dev_path = config.get('camera', 'device_path')
    try:
        if dev_path.startswith('/dev/video'):
            cam_idx = int(dev_path.replace('/dev/video', ''))
            cap = cv2.VideoCapture(cam_idx, cv2.CAP_V4L2)
        else:
            cap = cv2.VideoCapture(dev_path, cv2.CAP_V4L2)
    except Exception:
        cap = cv2.VideoCapture(dev_path, cv2.CAP_V4L2)

    if not cap.isOpened():
        print(f"Error: Could not open {dev_path}")
        sys.exit(1)

    print("\nGet ready! Look directly at the camera...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
        cap.read()

    print("Capturing frame...")
    frame, face = scan_face(cap, detector, timeout=2.0)
    cap.release()

    if face is None:
        print("Error: No face detected. Please try again.")
        sys.exit(1)

    print("Extracting geometry...")
    aligned_face = recognizer.alignCrop(frame, face)
    feature_vector = recognizer.feature(aligned_face)

    quantized_vector = np.round(feature_vector[0], 3).tolist()
    cipher = Fernet(get_hardware_key())
    payload = json.dumps({"version": "1.0", "embedding": quantized_vector}).encode('utf-8')
    encrypted_blob = cipher.encrypt(payload)

    os.makedirs(VAULT_DIR, exist_ok=True)
    vault_path = os.path.join(VAULT_DIR, f"{username}.enc")
    
    with open(vault_path, "wb") as f:
        f.write(encrypted_blob)
    os.chmod(vault_path, 0o600)

    print(f"\nENROLLMENT SUCCESSFUL for {username}!")
    print(f"Secure vault saved to {vault_path}")

def authenticate(username, config, is_pam=False):
    vault_path = os.path.join(VAULT_DIR, f"{username}.enc")
    
    if not os.path.exists(vault_path):
        if not is_pam: print(f"Error: No vault found for {username}. Run: sudo facelock enroll")
        log_auth(f"Authentication failed for {username}: No vault found", syslog.LOG_WARNING)
        sys.exit(1)

    try:
        with open(vault_path, "rb") as f:
            encrypted_blob = f.read()
        cipher = Fernet(get_hardware_key())
        decrypted_payload = cipher.decrypt(encrypted_blob)
        data = json.loads(decrypted_payload)
        stored_embedding = np.array(data["embedding"], dtype=np.float32)
    except InvalidToken:
        msg = f"SECURITY LOCKOUT: Incorrect hardware key for {username}'s vault."
        if not is_pam: print(msg)
        log_auth(msg, syslog.LOG_CRIT)
        sys.exit(1)

    if not is_pam: print("Scanning face... (Looking for you...)")
    detector, recognizer = init_ai_models()
    
    dev_path = config.get('camera', 'device_path')
    timeout = config.getfloat('camera', 'timeout')
    threshold = config.getfloat('security', 'threshold')
    
    if dev_path.startswith('/dev/video'):
        cap = cv2.VideoCapture(int(dev_path.replace('/dev/video', '')), cv2.CAP_V4L2)
    else:
        cap = cv2.VideoCapture(dev_path, cv2.CAP_V4L2)

    frame, face = scan_face(cap, detector, timeout=timeout)
    cap.release()

    if face is None:
        if not is_pam: print("Authentication Failed: No face detected.")
        log_auth(f"Authentication failed for {username}: No face detected within timeout", syslog.LOG_NOTICE)
        sys.exit(1)

    aligned_face = recognizer.alignCrop(frame, face)
    feature_vector = recognizer.feature(aligned_face)
    live_embedding = np.round(feature_vector[0], 3).astype(np.float32)

    score = recognizer.match(
        stored_embedding.reshape(1, 128),
        live_embedding.reshape(1, 128),
        cv2.FaceRecognizerSF_FR_COSINE
    )

    if score >= threshold:
        if not is_pam: print(f"\nACCESS GRANTED! (Score: {score:.4f})")
        log_auth(f"Authentication SUCCESS for {username} via face recognition (Score: {score:.4f})", syslog.LOG_INFO)
        sys.exit(0)
    else:
        if not is_pam: print(f"\nACCESS DENIED! Face does not match vault. (Score: {score:.4f})")
        log_auth(f"Authentication DENIED for {username}: Face mismatch (Score: {score:.4f})", syslog.LOG_WARNING)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Linux IR Camera Face Unlock")
    parser.add_argument("command", choices=["enroll", "test", "auth-pam", "config"])
    args = parser.parse_args()

    target_user = os.environ.get("PAM_USER", os.environ.get("SUDO_USER", os.environ.get("USER")))

    if os.geteuid() != 0 and args.command in ["enroll", "auth-pam", "config"]:
        print("Error: This command must be run as root (sudo facelock ...)")
        sys.exit(1)

    config = load_config()

    if args.command == "enroll":
        enroll(target_user, config)
    elif args.command == "auth-pam":
        authenticate(target_user, config, is_pam=True)
    elif args.command == "test":
        print(f"Testing authentication for {target_user} without triggering PAM...")
        authenticate(target_user, config, is_pam=False)
    elif args.command == "config":
        os.system(f"${{EDITOR:-nano}} {CONFIG_FILE}")

if __name__ == "__main__":
    main()
