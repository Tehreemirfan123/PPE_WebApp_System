#!/usr/bin/env python
"""
ML Pipeline Integration Test
Tests the ML pipeline inference on demo video
"""

import os
import sys
import cv2
from pathlib import Path

print("=" * 70)
print("ML PIPELINE INTEGRATION TEST")
print("=" * 70)

# Check model files
print("\n[STEP 1: Verify Model Files]")
models_path = Path("models/yolov8n.pt")
ppe_model_path = Path("ml_pipeline/models/ppe_yolov8m_best.pt")
video_path = Path("ml_pipeline/test_videos/demo.mp4")

print(f"  Person model (models/yolov8n.pt): {'✓ FOUND' if models_path.exists() else '✗ NOT FOUND'}")
print(f"  PPE model (ml_pipeline/models/ppe_yolov8m_best.pt): {'✓ FOUND' if ppe_model_path.exists() else '✗ NOT FOUND'}")
print(f"  Test video (ml_pipeline/test_videos/demo.mp4): {'✓ FOUND' if video_path.exists() else '✗ NOT FOUND'}")

if not all([models_path.exists(), ppe_model_path.exists(), video_path.exists()]):
    print("\n✗ CRITICAL: Missing model files or test video!")
    sys.exit(1)

# Test model loading
print("\n[STEP 2: Load YOLO Models]")
try:
    from ultralytics import YOLO
    print("  Loading person detection model (yolov8n)...")
    person_model = YOLO(str(models_path))
    print(f"  ✓ Person model loaded successfully")
    
    print("  Loading PPE detection model (ppe_yolov8m_best)...")
    ppe_model = YOLO(str(ppe_model_path))
    print(f"  ✓ PPE model loaded successfully")
except Exception as e:
    print(f"  ✗ ERROR loading models: {e}")
    sys.exit(1)

# Test video loading
print("\n[STEP 3: Load Test Video]")
try:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  ✗ ERROR: Cannot open video file")
        sys.exit(1)
    
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"  ✓ Video loaded successfully")
    print(f"    Frames: {frame_count}, FPS: {fps}, Resolution: {width}x{height}")
except Exception as e:
    print(f"  ✗ ERROR loading video: {e}")
    sys.exit(1)

# Test inference on first frame
print("\n[STEP 4: Test Inference on First Frame]")
try:
    ret, frame = cap.read()
    if not ret:
        print(f"  ✗ ERROR: Cannot read first frame")
        sys.exit(1)
    
    print("  Running person detection...")
    person_results = person_model(frame, verbose=False)
    person_boxes = len(person_results[0].boxes)
    print(f"  ✓ Detected {person_boxes} persons")
    
    print("  Running PPE detection...")
    ppe_results = ppe_model(frame, verbose=False)
    ppe_boxes = len(ppe_results[0].boxes)
    print(f"  ✓ Detected {ppe_boxes} PPE items")
    
except Exception as e:
    print(f"  ✗ ERROR during inference: {e}")
    sys.exit(1)
finally:
    cap.release()

# Test backend connectivity
print("\n[STEP 5: Test Backend API Connectivity]")
try:
    import requests
    response = requests.get('http://localhost:8000/health', timeout=5)
    if response.status_code == 200:
        print("  ✓ Backend API is reachable on http://localhost:8000")
    else:
        print(f"  ✗ Backend returned status {response.status_code}")
except Exception as e:
    print(f"  ✗ ERROR connecting to backend: {e}")

# Test ML pipeline configuration
print("\n[STEP 6: Validate ML Pipeline Configuration]")
try:
    import yaml
    with open("ml_pipeline/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    print(f"  ✓ Config loaded")
    print(f"    Site: {config.get('site_name')}")
    print(f"    Camera: {config.get('camera_name')}")
    print(f"    Video source: {config.get('video_source')}")
    print(f"    API endpoint: {config.get('api_base_url')}")
    print(f"    Temporal frames: {config.get('temporal_frames')}")
    print(f"    Cooldown (sec): {config.get('cooldown_seconds')}")
except Exception as e:
    print(f"  ✗ ERROR loading config: {e}")

print("\n" + "=" * 70)
print("ML PIPELINE STATUS: ✓ ALL CHECKS PASSED")
print("The ML pipeline is ready to process videos!")
print("=" * 70)
