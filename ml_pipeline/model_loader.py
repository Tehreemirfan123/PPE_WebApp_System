from ultralytics import YOLO
import numpy as np
import yaml
# import face_recognition  # Temporarily disabled

class ModelLoader:
    def __init__(self, config):
        self.config = config
        self.person_model = YOLO(config['person_model'])
        self.ppe_model = YOLO(config['ppe_model'])
        
        self.person_conf = config['person_conf']
        self.ppe_conf = config['ppe_conf']
        
        # Load labels from data.yaml
        with open("ml_pipeline/data.yaml", "r") as f:
            data = yaml.safe_load(f)
            self.class_names = data.get("names", {})
            
        # Define violation classes IDs (everything with "no_")
        self.violation_classes = {
            id for id, name in self.class_names.items() if str(name).startswith("no_")
        }

    def detect_persons(self, frame: np.ndarray) -> list[dict]:
        """
        Returns list of person bounding boxes with stable track IDs:
        [{"bbox": [x1, y1, x2, y2], "conf": 0.92, "track_id": 1}, ...]
        """
        # use .track() to persist IDs across frames
        results = self.person_model.track(frame, persist=True, conf=self.person_conf, classes=[0], verbose=False)[0]
        
        persons = []
        if results.boxes.id is not None:
            ids = results.boxes.id.cpu().numpy().astype(int)
            for box, track_id in zip(results.boxes, ids):
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                persons.append({
                    "bbox": [x1, y1, x2, y2],
                    "conf": float(box.conf[0]),
                    "track_id": int(track_id)
                })
        else:
            # Fallback if no tracks are active yet
            for i, box in enumerate(results.boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                persons.append({
                    "bbox": [x1, y1, x2, y2],
                    "conf": float(box.conf[0]),
                    "track_id": -(i + 1) # Temporary negative ID
                })
        return persons

    def detect_ppe_in_roi(self, frame: np.ndarray, bbox: list) -> list[dict]:
        """
        Crops person ROI, runs PPE model, returns detections:
        [{"class_id": 10, "class_name": "no_hardhat", "conf": 0.87, "is_violation": True}, ...]
        """
        x1, y1, x2, y2 = bbox
        
        # Pad slightly to capture context (e.g. hardhat slightly above head)
        h, w = frame.shape[:2]
        pad = 15
        px1, py1 = max(0, x1 - pad), max(0, y1 - pad)
        px2, py2 = min(w, x2 + pad), min(h, y2 + pad)
        
        roi = frame[py1:py2, px1:px2]
        if roi.size == 0:
            return []

        results = self.ppe_model(roi, conf=self.ppe_conf, verbose=False)[0]
        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            detections.append({
                "class_id": cls_id,
                "class_name": self.class_names.get(cls_id, "unknown"),
                "conf": float(box.conf[0]),
                "is_violation": cls_id in self.violation_classes
            })
        return detections
        
    def detect_all_ppe(self, frame: np.ndarray) -> list[dict]:
        """
        Runs PPE model on the full frame once and returns all detections:
        [{"class_id": 10, "class_name": "no_hardhat", "conf": 0.87, "bbox": [x1, y1, x2, y2], "is_violation": True}, ...]
        """
        results = self.ppe_model(frame, conf=self.ppe_conf, verbose=False)[0]
        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            detections.append({
                "class_id": cls_id,
                "class_name": self.class_names.get(cls_id, "unknown"),
                "conf": float(box.conf[0]),
                "bbox": [x1, y1, x2, y2],
                "is_violation": cls_id in self.violation_classes
            })
        return detections
        
    def extract_face_embedding(self, frame: np.ndarray, bbox: list) -> list:
        """
        Optional: extract 512-d face embedding from ROI
        """
        x1, y1, x2, y2 = bbox
        roi = frame[y1:y2, x1:x2]
        # Convert BGR to RGB for face_recognition
        rgb_roi = roi[:, :, ::-1]
        
        face_locations = face_recognition.face_locations(rgb_roi, model="hog")
        if face_locations:
            face_encodings = face_recognition.face_encodings(rgb_roi, face_locations)
            if face_encodings:
                return face_encodings[0].tolist()
        return None
