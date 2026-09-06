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
import shutil
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

# System Paths
CONFIG_FILE = "/etc/infralock/config.ini"
VAULT_DIR = "/var/lib/infralock"

def get_models_dir():
    # If running as a compiled PyInstaller binary, unpack resources from temp folder
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'models')
    return "/usr/share/infralock/models"

def load_config():
    config = configparser.ConfigParser()
    config.read_dict({
        'camera': {'device_path': '/dev/video2', 'timeout': '5.0', 'shutter_delay': '2.0'},
        'security': {'threshold': '0.363'}
    })
    config.read(CONFIG_FILE)
    return config

def log_auth(message, level=syslog.LOG_INFO):
    syslog.openlog(ident="infralock", facility=syslog.LOG_AUTH)
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

def init_ai_models(input_size):
    models_dir = get_models_dir()
    yunet_path = os.path.join(models_dir, "yunet.onnx")
    sface_path = os.path.join(models_dir, "sface.onnx")
    
    if not os.path.exists(yunet_path) or not os.path.exists(sface_path):
        print(f"Error: AI models not found in {models_dir}.")
        sys.exit(1)
        
    detector = cv2.FaceDetectorYN.create(yunet_path, "", input_size)
    recognizer = cv2.FaceRecognizerSF.create(sface_path, "")
    return detector, recognizer

def open_camera(dev_path):
    try:
        if dev_path.startswith('/dev/video'):
            cam_idx = int(dev_path.replace('/dev/video', ''))
            return cv2.VideoCapture(cam_idx, cv2.CAP_V4L2)
        else:
            return cv2.VideoCapture(dev_path, cv2.CAP_V4L2)
    except Exception:
        return cv2.VideoCapture(dev_path, cv2.CAP_V4L2)

def scan_face(cap, detector, timeout=5.0):
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        ret, frame = cap.read()
        if not ret:
            continue
            
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            
        h, w, _ = frame.shape
        new_h = int(np.ceil(h / 32.0) * 32)
        new_w = int(np.ceil(w / 32.0) * 32)
        
        if new_h != h or new_w != w:
            pad_frame = np.zeros((new_h, new_w, 3), dtype=np.uint8)
            pad_frame[:h, :w, :] = frame
            ret, faces = detector.detect(pad_frame)
        else:
            ret, faces = detector.detect(frame)
            
        if faces is not None and len(faces) > 0:
            return frame, faces[0]
            
    return None, None

def enroll(username, config):
    print(f"Enrolling face for user: {username}")
    dev_path = config.get('camera', 'device_path')
    cap = open_camera(dev_path)

    if not cap.isOpened():
        print(f"Error: Could not open {dev_path}")
        sys.exit(1)

    ret, frame = cap.read()
    if not ret:
        print("Error: Camera opened but failed to capture a test frame.")
        sys.exit(1)
        
    h, w = frame.shape[:2]
    new_h = int(np.ceil(h / 32.0) * 32)
    new_w = int(np.ceil(w / 32.0) * 32)
    detector, recognizer = init_ai_models((new_w, new_h))

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
    os.chmod(VAULT_DIR, 0o755)
    
    vault_path = os.path.join(VAULT_DIR, f"{username}.enc")
    
    with open(vault_path, "wb") as f:
        f.write(encrypted_blob)
    
    import pwd
    try:
        user_info = pwd.getpwnam(username)
        os.chown(vault_path, user_info.pw_uid, user_info.pw_gid)
    except KeyError:
        pass
        
    os.chmod(vault_path, 0o600)

    print(f"\nENROLLMENT SUCCESSFUL for {username}!")
    print(f"Secure vault saved to {vault_path}")

def authenticate(username, config, is_pam=False):
    vault_path = os.path.join(VAULT_DIR, f"{username}.enc")
    
    if not os.path.exists(vault_path):
        if not is_pam: print(f"Error: No vault found for {username}. Run: sudo infralock enroll")
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

    dev_path = config.get('camera', 'device_path')
    timeout = config.getfloat('camera', 'timeout')
    threshold = config.getfloat('security', 'threshold')
    shutter_delay = config.getfloat('camera', 'shutter_delay', fallback=2.0)
    
    if shutter_delay > 0:
        if not is_pam: print(f"\n⏳ Please open your camera shutter... (Waiting {shutter_delay}s)")
        time.sleep(shutter_delay)
    
    cap = open_camera(dev_path)
    if not cap.isOpened():
        if not is_pam: print("Error: Could not open camera.")
        log_auth("Authentication failed: Camera unavailable.", syslog.LOG_ERR)
        sys.exit(1)

    ret, frame = cap.read()
    if not ret:
        if not is_pam: print("Error: Failed to read from camera.")
        sys.exit(1)
        
    h, w = frame.shape[:2]
    new_h = int(np.ceil(h / 32.0) * 32)
    new_w = int(np.ceil(w / 32.0) * 32)
    detector, recognizer = init_ai_models((new_w, new_h))

    if not is_pam: print("Scanning face... (Looking for you...)")
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

def manage_pam(action="install"):
    PAM_LINE = "auth sufficient pam_exec.so stdout seteuid /usr/local/bin/infralock auth-pam\n"
    targets = [
        "/etc/pam.d/sudo",
        "/etc/pam.d/gdm-password",
        "/etc/pam.d/lightdm",
        "/etc/pam.d/cinnamon-screensaver",
        "/etc/pam.d/sddm",
        "/etc/pam.d/su"
    ]
    
    for target in targets:
        if not os.path.exists(target):
            continue
            
        with open(target, 'r') as f:
            lines = f.readlines()
            
        if action == "install":
            if any("infralock" in line for line in lines):
                print(f"Already installed in {target}")
                continue
                
            print(f"Injecting into {target}...")
            # Insert after the first comment block, or at the top
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('#'):
                    insert_idx = i
                    break
            lines.insert(insert_idx, PAM_LINE)
            
        elif action == "uninstall":
            if not any("infralock" in line for line in lines):
                continue
            print(f"Removing from {target}...")
            lines = [l for l in lines if "infralock" not in l]
            
        # Create backup and write
        shutil.copy(target, f"{target}.bak")
        with open(target, 'w') as f:
            f.writelines(lines)
            
    print("PAM configuration updated successfully!")

def run_gui():
    import tkinter as tk
    from tkinter import messagebox
    import subprocess

    def run_cmd(cmd_list):
        # We use pkexec to ask for password if root is needed
        try:
            subprocess.run(["pkexec", "/usr/local/bin/infralock"] + cmd_list, check=True)
            messagebox.showinfo("Success", "Operation completed successfully!")
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", "Operation failed or was cancelled.")

    root = tk.Tk()
    root.title("Infra Lock Control Panel")
    root.geometry("400x300")
    
    tk.Label(root, text="🔒 Infra Lock Air-Gapped Security", font=("Arial", 14, "bold")).pack(pady=20)
    
    tk.Button(root, text="📸 Enroll Face", command=lambda: run_cmd(["enroll"]), height=2, width=30).pack(pady=5)
    tk.Button(root, text="✅ Test Authentication", command=lambda: subprocess.run(["infralock", "test"]), height=2, width=30).pack(pady=5)
    tk.Button(root, text="⚙️ Enable System-Wide Auth", command=lambda: run_cmd(["install-pam"]), height=2, width=30).pack(pady=5)
    tk.Button(root, text="❌ Disable System-Wide Auth", command=lambda: run_cmd(["uninstall-pam"]), height=2, width=30).pack(pady=5)
    
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Linux IR Camera Face Unlock")
    parser.add_argument("command", choices=["enroll", "test", "auth-pam", "config", "install-pam", "uninstall-pam", "gui"])
    args = parser.parse_args()

    target_user = os.environ.get("PAM_USER", os.environ.get("SUDO_USER", os.environ.get("USER")))

    if os.geteuid() != 0 and args.command in ["enroll", "config", "install-pam", "uninstall-pam"]:
        print("Error: This command must be run as root (sudo infralock ...)")
        sys.exit(1)

    # Initialize config file gracefully if missing
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write("[camera]\ndevice_path = /dev/video2\ntimeout = 5.0\n[security]\nthreshold = 0.363\n")

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
    elif args.command == "install-pam":
        manage_pam("install")
    elif args.command == "uninstall-pam":
        manage_pam("uninstall")
    elif args.command == "gui":
        run_gui()

if __name__ == "__main__":
    main()
