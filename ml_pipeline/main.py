import cv2
import yaml
import sys
from backend_client import BackendClient
from compliance import ComplianceLogic
from model_loader import ModelLoader
from face_module import FaceRecognizer, process_faces, match_person_to_face
from backend.database import SessionLocal

def load_config(path="ml_pipeline/config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)

def run():
    print("[INFO] Starting ML Pipeline...")
    config = load_config()
    
    # Initialize backend client
    client = BackendClient(config)
    if not client.authenticate():
        print("[ERROR] Cannot proceed without backend authentication.")
        return
        
    # Get required PPE for this site
    required_ppe = client.get_required_ppe(config["site_name"])
    print(f"[INFO] Required PPE for '{config['site_name']}': {required_ppe}")
    
    if not required_ppe:
        print("[WARN] No required PPE found for this site. Ensure the site exists and is configured in the backend.")
    
    # ─── INITIALIZE FACE RECOGNITION CACHE ────────────────────────────────────
    print("[INFO] Initializing Face Recognition Database Cache...")
    face_recognizer = FaceRecognizer(db_session_factory=SessionLocal)
    
    # Initialize ML models and compliance logic
    print("[INFO] Loading models...")
    models = ModelLoader(config)
    compliance = ComplianceLogic(config)
    
    # Open Video Source
    source = config["video_source"]
    cap = cv2.VideoCapture(source)
    
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video source: {source}")
        return

    print(f"[INFO] Processing video: {source}")
    print("[INFO] DEDUPLICATION ENABLED: Images saved only once per violation (grace period: 30s)")
    
    # Initialize display window early and force it to open topmost on screen
    show_display = config.get("show_display", True)
    if show_display:
        cv2.namedWindow("PPE Monitor - Real-time Detection", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("PPE Monitor - Real-time Detection", 1280, 720)
        try:
            cv2.setWindowProperty("PPE Monitor - Real-time Detection", cv2.WND_PROP_TOPMOST, 1)
        except Exception:
            pass # Graceful fallback if topmost property is not supported on the OS version
        cv2.waitKey(1)
    
    frame_count = 0
    violations_logged = 0
    images_saved = 0
    
    # ─── Frame-Skipping & Display Optimization ───
    skip_frames = config.get("skip_frames", 1)
    cached_drawing_actions = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[INFO] End of video or stream interrupted.")
            break
        
        frame_count += 1
        
        # Check if we should run heavy YOLO & Face inference on this frame
        should_process = (frame_count % skip_frames == 0) or (frame_count == 1)
        
        if should_process:
            # Convert frame to RGB once (DeepFace and YOLO handle RGB inputs best)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # ─── STEP 1: DETECT AND IDENTIFY FACES ────────────────────────────
            face_locations, face_names = process_faces(frame_rgb, face_recognizer)
            
            # 2. Detect Persons
            persons = models.detect_persons(frame)
            
            # 3. Detect all PPE at once
            all_ppe = models.detect_all_ppe(frame)
            
            # ─── Dynamic Site Inference (Optional) ───
            if config.get("auto_detect_site", True):
                if all_ppe:
                    inferred = compliance.infer_site(all_ppe)
                    if inferred and inferred != config["site_name"]:
                        print(f"[INFO] Switching to inferred site: {inferred}")
                        config["site_name"] = inferred
                        client.config["site_name"] = inferred
                        compliance.site_name = inferred
                        required_ppe = client.get_required_ppe(inferred)
                        print(f"[INFO] New requirements for '{inferred}': {required_ppe}")

            # Map PPE detections to persons by overlap area
            person_detections = {p["track_id"]: [] for p in persons}
            
            for ppe in all_ppe:
                bx1, by1, bx2, by2 = ppe["bbox"]
                ppe_area = (bx2 - bx1) * (by2 - by1)
                if ppe_area <= 0:
                    continue
                
                best_person_id = None
                best_overlap = 0.0
                
                for person in persons:
                    px1, py1, px2, py2 = person["bbox"]
                    # Calculate intersection
                    ix1 = max(px1, bx1)
                    iy1 = max(py1, by1)
                    ix2 = min(px2, bx2)
                    iy2 = min(py2, by2)
                    
                    if ix2 > ix1 and iy2 > iy1:
                        inter_area = (ix2 - ix1) * (iy2 - iy1)
                        overlap = inter_area / ppe_area
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_person_id = person["track_id"]
                
                # If the best match has > 30% overlap, assign it to that person
                if best_person_id is not None and best_overlap > 0.3:
                    person_detections[best_person_id].append(ppe)

            # Track violations across all persons in this frame
            frame_violations_to_log = []
            highest_conf = 0.0
            
            # Reset drawing cache for this processed frame
            cached_drawing_actions = []

            for person in persons:
                track_id = person["track_id"]
                bbox = person["bbox"]
                avg_conf = person["conf"]
                if avg_conf > highest_conf:
                    highest_conf = avg_conf
                
                # ─── STEP 2: MATCH PERSON TO RECOGNIZED FACE ──────────────────
                worker_identity = match_person_to_face(bbox, face_locations, face_names)
                
                # Retrieve mapped PPE detections for this person
                detections = person_detections[track_id]
                
                # Apply compliance logic
                detections = compliance.resolve_conflicts(detections)
                missing = compliance.evaluate_policy(detections, required_ppe)
                
                # Temporal smoothing (must persist for 5 frames)
                confirmed = compliance.update_temporal(track_id, missing)
                
                # Duplicate suppression (cooldown rule)
                final_violations = compliance.apply_cooldown(track_id, confirmed)
                
                # Draw bounding boxes and labels for the UI and saved frame
                x1, y1, x2, y2 = bbox
                color = (0, 0, 255) if missing else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # ─── STEP 3: UPDATE BOUNDING BOX LABELS ───────────────────────
                # Build a unified label containing worker name (if found) and track metadata
                identity_str = f"[{worker_identity}] " if worker_identity != "Unknown Worker" else ""
                
                if missing:
                    label = f"{identity_str}ID:{track_id} " + ", ".join(missing[:2])
                    cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
                    # Collect violations to log to DB
                    if final_violations:
                        frame_violations_to_log.extend(final_violations)
                else:
                    # If they are fully compliant, still show their name above the green box!
                    if worker_identity != "Unknown Worker":
                        label = worker_identity
                        cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    else:
                        label = f"ID:{track_id}"
                        cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                        
                # Add to drawing cache
                cached_drawing_actions.append({
                    "bbox": (x1, y1, x2, y2),
                    "color": color,
                    "label": label
                })

            # Save frame and log to DB ONCE per frame
            if frame_violations_to_log:
                # Check if this exact frame violation set should trigger an image save
                should_save_image = compliance.should_save_violation_image(frame_violations_to_log)
                
                if should_save_image:
                    print(f"[ALERT] New violations in frame: {frame_violations_to_log}")
                    client.log_violation(frame, frame_violations_to_log, highest_conf, should_save_image=True)
                    violations_logged += 1
                    images_saved += 1
                else:
                    # Log violation to database but skip saving the duplicate image
                    client.log_violation(frame, frame_violations_to_log, highest_conf, should_save_image=False)
                    violations_logged += 1
        else:
            # skipped frame: apply cached drawing annotations
            for action in cached_drawing_actions:
                x1, y1, x2, y2 = action["bbox"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), action["color"], 2)
                if action["label"]:
                    # Keep color matching the original cached alert state
                    cv2.putText(frame, action["label"], (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, action["color"], 2)

        # 3. Display the frame
        if config.get("show_display", True):
            stats_text = f"Frame: {frame_count} | Logged: {violations_logged} | Images: {images_saved}"
            cv2.putText(frame, stats_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            h, w = frame.shape[:2]
            if w > 1280:
                scale = 1280 / w
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
                
            cv2.imshow("PPE Monitor - Real-time Detection", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("[INFO] Quit requested by user.")
                break

    cap.release()
    cv2.destroyAllWindows()
    
    # Print final statistics
    print("\n" + "="*70)
    print("PIPELINE EXECUTION COMPLETED")
    print("="*70)
    print(f"Total Frames Processed: {frame_count}")
    print(f"Violations Logged (DB): {violations_logged}")
    print(f"Images Saved: {images_saved}")
    print(f"Deduplication Efficiency: {((violations_logged - images_saved) / violations_logged * 100) if violations_logged > 0 else 0:.1f}% duplicate frames skipped")
    print(f"Compliance Stats: {compliance.get_saved_violations_stats()}")
    print("="*70)

if __name__ == "__main__":
    run()
