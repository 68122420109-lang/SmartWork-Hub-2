from __future__ import annotations

import base64
import hmac
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import cv2
import numpy as np
from flask import current_app
from PIL import Image
import io

# Initialize cascades
CASCADE_FACE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
CASCADE_EYE_PATH = cv2.data.haarcascades + 'haarcascade_eye.xml'

face_cascade = cv2.CascadeClassifier(CASCADE_FACE_PATH)
eye_cascade = cv2.CascadeClassifier(CASCADE_EYE_PATH)


def get_face_upload_folder() -> Path:
    """Return secure folder path for face reference images."""
    base_dir = Path(current_app.config.get('BASE_DIR', Path.cwd()))
    folder = base_dir / 'app' / 'static' / 'uploads' / 'face_records'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def decode_base64_image(image_data: str) -> Tuple[bool, str, Optional[np.ndarray]]:
    """Decode base64 image data to OpenCV BGR numpy array."""
    if not image_data:
        return False, "ไม่พบข้อมูลรูปภาพ", None

    try:
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        raw_bytes = base64.b64decode(image_data)
        if len(raw_bytes) > 5 * 1024 * 1024:
            return False, "ขนาดไฟล์รูปภาพเกิน 5 MB", None

        # Verify image using PIL
        pil_img = Image.open(io.BytesIO(raw_bytes))
        pil_img.verify()

        # Reload for reading as numpy array
        pil_img = Image.open(io.BytesIO(raw_bytes)).convert('RGB')
        rgb_arr = np.array(pil_img)
        bgr_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
        return True, "ถอดรหัสรูปภาพสำเร็จ", bgr_arr
    except Exception as exc:
        return False, f"รูปแบบไฟล์รูปภาพไม่ถูกต้อง: {str(exc)}", None


def detect_face_in_image(bgr_img: np.ndarray) -> Tuple[bool, str, Optional[Tuple[int, int, int, int]]]:
    """Detect single face in image. Returns success, message, and bounding box (x, y, w, h)."""
    if bgr_img is None or bgr_img.size == 0:
        return False, "ภาพว่างเปล่าหรือไม่ถูกต้อง", None

    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.15,
        minNeighbors=5,
        minSize=(70, 70),
        flags=cv2.CASCADE_SCALE_IMAGE
    )

    if len(faces) == 0:
        return False, "ไม่พบใบหน้าในภาพ กรุณาจัดตำแหน่งใบหน้าให้อยู่ตรงกลางกรอบและมีแสงสว่างเพียงพอ", None
    if len(faces) > 1:
        return False, "ตรวจพบใบหน้ามากกว่า 1 คนในกล้อง กรุณาอยู่ในเฟรมเพียงคนเดียว", None

    return True, "ตรวจพบใบหน้า", tuple(faces[0])


def extract_face_features(bgr_img: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple[np.ndarray, np.ndarray]:
    """Extract standard 128x128 normalized face crop and feature vector."""
    x, y, w, h = bbox
    # Add small margin
    margin_w = int(w * 0.1)
    margin_h = int(h * 0.1)
    x1 = max(0, x - margin_w)
    y1 = max(0, y - margin_h)
    x2 = min(bgr_img.shape[1], x + w + margin_w)
    y2 = min(bgr_img.shape[0], y + h + margin_h)

    crop = bgr_img[y1:y2, x1:x2]
    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    crop_resized = cv2.resize(crop_gray, (128, 128), interpolation=cv2.INTER_AREA)
    crop_eq = cv2.equalizeHist(crop_resized)

    # Compute block-based multi-cell features (8x8 grid -> 64 blocks of 16x16)
    features = []
    for r in range(8):
        for c in range(8):
            block = crop_eq[r*16:(r+1)*16, c*16:(c+1)*16]
            mean_val = float(np.mean(block))
            std_val = float(np.std(block))
            # Histogram of block
            hist = cv2.calcHist([block], [0], None, [4], [0, 256]).flatten()
            features.extend([mean_val, std_val] + list(hist))

    feat_arr = np.array(features, dtype=np.float32)
    norm = np.linalg.norm(feat_arr)
    if norm > 0:
        feat_arr = feat_arr / norm

    return crop_eq, feat_arr


def compare_faces(candidate_feat: np.ndarray, candidate_crop: np.ndarray,
                  ref_feat: np.ndarray, ref_crop: np.ndarray) -> Tuple[bool, float, str]:
    """Compare candidate face with reference face. Returns (is_match, similarity_score, message)."""
    # 1. Cosine similarity of feature vectors
    cosine_sim = float(np.dot(candidate_feat, ref_feat))
    # Bound between 0 and 1
    cosine_score = max(0.0, min(1.0, (cosine_sim + 1.0) / 2.0))

    # 2. Template cross-correlation on normalized crops
    res = cv2.matchTemplate(candidate_crop, ref_crop, cv2.TM_CCOEFF_NORMED)
    template_score = float(max(0.0, res[0][0]))

    # Combined weighted score (60% feature vector, 40% template correlation)
    final_score = (cosine_score * 0.6) + (template_score * 0.4)
    # Threshold for matching
    THRESHOLD = 0.72

    if final_score >= THRESHOLD:
        return True, round(final_score, 3), f"ยืนยันตัวตนสำเร็จ (ความเหมือน: {round(final_score * 100, 1)}%)"
    else:
        return False, round(final_score, 3), f"ใบหน้าไม่ตรงกับข้อมูลที่ลงทะเบียนไว้ (ความเหมือน: {round(final_score * 100, 1)}% ไม่ถึงเกณฑ์ 72%)"


def generate_liveness_challenge() -> Dict[str, Any]:
    """Generate a cryptographic time-limited liveness challenge for camera capture."""
    secret = current_app.config.get('SECRET_KEY', 'smartwork-hub-secret').encode('utf-8')
    timestamp = int(time.time())
    nonce = hashlib.sha256(os.urandom(16)).hexdigest()[:12]
    
    # Predefined natural micro-action prompts
    challenges = [
        {"action": "straight", "text": "มองตรงที่กล้องและยิ้มเล็กน้อย"},
        {"action": "tilt", "text": "มองตรงแล้วเอียงศีรษะเล็กน้อย"},
        {"action": "blink", "text": "มองตรงที่กล้องแล้วกะพริบตาหนึ่งครั้ง"},
    ]
    # Pick challenge deterministically or semi-randomly
    selected = challenges[timestamp % len(challenges)]

    payload = f"{timestamp}:{nonce}:{selected['action']}"
    signature = hmac.new(secret, payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    token = f"{payload}:{signature}"

    return {
        "challenge_token": token,
        "action": selected['action'],
        "instruction": selected['text'],
        "expires_in": 60
    }


def verify_liveness_challenge(token: str) -> Tuple[bool, str, Optional[str]]:
    """Verify that the challenge token is valid, unexpired, and not tampered with."""
    if not token or ':' not in token:
        return False, "รหัสการตรวจสอบ (Challenge Token) ไม่ถูกต้อง", None

    parts = token.split(':')
    if len(parts) != 4:
        return False, "รูปแบบ Challenge Token ไม่ถูกต้อง", None

    timestamp_str, nonce, action, sig = parts
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False, "เวลาใน Challenge Token ไม่ถูกต้อง", None

    # Check expiry (valid for 90 seconds)
    now = int(time.time())
    if now - timestamp > 90:
        return False, "รหัสการตรวจสอบหมดอายุแล้ว กรุณาสแกนใบหน้าใหม่อีกครั้ง", None
    if timestamp > now + 30:
        return False, "เวลาของรหัสตรวจสอบล่วงหน้าผิดปกติ", None

    secret = current_app.config.get('SECRET_KEY', 'smartwork-hub-secret').encode('utf-8')
    expected_payload = f"{timestamp_str}:{nonce}:{action}"
    expected_sig = hmac.new(secret, expected_payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16]

    if not hmac.compare_digest(sig, expected_sig):
        return False, "ลายมือชื่อของ Challenge Token ไม่ถูกต้อง (Anti-Tamper)", None

    return True, "Challenge ถูกต้อง", action
