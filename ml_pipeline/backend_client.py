import requests
import datetime
import cv2
import os
from pathlib import Path

class BackendClient:
    def __init__(self, config):
        self.config = config
        self.api_base_url = config['api_base_url']
        self.token = None
        
    def authenticate(self):
        """Authenticates with the FastAPI backend to get a JWT token."""
        try:
            resp = requests.post(
                f"{self.api_base_url}/auth/login",
                json={"email": self.config["api_email"], "password": self.config["api_password"]},
                timeout=10
            )
            resp.raise_for_status()
            self.token = resp.json()["access_token"]
            print("[INFO] Successfully authenticated with the backend.")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to authenticate: {e}")
            return False

    def get_required_ppe(self, site_name: str) -> list[str]:
        """Fetch mandatory PPE items for the site from the backend."""
        if not self.token:
            print("[ERROR] Not authenticated.")
            return []
            
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            resp = requests.get(f"{self.api_base_url}/sites/{site_name}", headers=headers, timeout=5)
            if resp.status_code == 200:
                reqs = resp.json().get("requirements", [])
                return [r["ppe_item"] for r in reqs]
            else:
                print(f"[WARN] Failed to fetch requirements for {site_name}: {resp.status_code} {resp.text}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch requirements: {e}")
            return []

    def log_violation(self, frame, missing_items, conf, should_save_image=True):
        """
        Saves the violation frame and POSTs detection event + individual violations.
        
        Args:
            frame: Video frame (OpenCV image)
            missing_items: List of missing PPE items in the frame
            conf: Confidence score
            should_save_image: Boolean indicating if image should be saved (deduplication check)
        """
        if not self.token:
            print("[ERROR] Not authenticated.")
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        # Only save image and log to DB if deduplication logic says to
        if not should_save_image:
            print(f"[SKIPPED] Duplicate violation. Skipping DB and Image.")
            return
            
        # 1. Save the annotated frame locally so the backend can serve it statically
        save_dir = Path(self.config["saved_violations_dir"])
        save_dir.mkdir(parents=True, exist_ok=True)
        
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        img_filename = f"violation_{ts}.jpg"
        img_path = save_dir / img_filename
        
        cv2.imwrite(str(img_path), frame)
        print(f"[SAVED IMAGE] {img_filename}")

        # 2. POST detection event
        event_payload = {
            "camera_name": self.config["camera_name"],
            "site_name":   self.config["site_name"],
            "detected_by": "yolov8m",
            "image_path":  img_filename,  # Only filename if saved, None otherwise
            "confidence_score": conf,
            "detected_ppe": [],
            "missing_ppe":  missing_items,
        }
        
        try:
            resp = requests.post(f"{self.api_base_url}/detection-event/", json=event_payload, headers=headers, timeout=10)
            if resp.status_code != 201:
                print(f"[WARN] Failed to log detection event: {resp.status_code} {resp.text}")
                return
                
            event_id = resp.json()["id"]

            # 3. POST individual violations for each missing item
            # Deduplicate items to avoid posting identical violations twice in the same event
            unique_missing = list(set(missing_items))
            for item in unique_missing:
                # Remove "no_" prefix if it exists to get the clean item name for the DB
                clean_item = item[3:] if item.startswith("no_") else item
                
                violation_payload = {
                    "event_id": event_id,
                    "site_name": self.config["site_name"],
                    "camera_name": self.config["camera_name"],
                    "missing_item": clean_item,
                    "confidence_score": conf,
                }
                v_resp = requests.post(f"{self.api_base_url}/violation/", json=violation_payload, headers=headers, timeout=10)
                if v_resp.status_code == 201:
                    print(f"[LOGGED VIOLATION] {clean_item}")
                else:
                    print(f"[WARN] Failed to log violation {clean_item}: {v_resp.text}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to post violation data: {e}")