# Add these at the very top — before anything else
import os
import sys
import numpy as np
import yaml
from ultralytics import YOLO
import openvino as ov

_ML_DIR = os.path.dirname(os.path.abspath(__file__))

@staticmethod
def _resolve_data_yaml(config: dict) -> str:
    candidates = [
        config.get("data_yaml", ""),
        os.path.join(_ML_DIR, "data.yaml"),
        os.path.join(_ML_DIR, "..", "data.yaml"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    raise FileNotFoundError(f"data.yaml not found. Tried: {candidates}")

class _OpenVINOModel:
    """
    Thin wrapper around OpenVINO runtime that mimics the Ultralytics YOLO
    inference interface used by ModelLoader (detect_persons, detect_all_ppe).
    Returns results in the same format as YOLO() would.
    """

    def __init__(self, xml_path: str):
        #from openvino.runtime import Core
        ie = ov.Core()
        self.model     = ie.compile_model(xml_path, "CPU")
        self.output    = self.model.output(0)
        self._xml_path = xml_path
        # Read imgsz from metadata.yaml next to the xml
        self.imgsz = 640
        meta = os.path.join(os.path.dirname(xml_path), "metadata.yaml")
        if os.path.exists(meta):
            with open(meta) as f:
                md = yaml.safe_load(f)
                sz = md.get("imgsz", [640, 640])
                self.imgsz = sz[0] if isinstance(sz, list) else sz

    def __call__(self, frame: np.ndarray, conf: float = 0.5, verbose=False):
        return self._infer(frame, conf)

    def track(self, frame: np.ndarray, persist=True, conf: float = 0.5,
              classes=None, verbose=False):
        return self._infer(frame, conf, classes=classes)

    def _infer(self, frame: np.ndarray, conf: float, classes=None):
        import cv2

        h0, w0 = frame.shape[:2]
        sz = self.imgsz

        # Letterbox resize
        blob = cv2.resize(frame, (sz, sz))
        blob = blob[:, :, ::-1].transpose(2, 0, 1)          # BGR→RGB, HWC→CHW
        blob = np.ascontiguousarray(blob, dtype=np.float32) / 255.0
        blob = blob[np.newaxis]                               # add batch dim

        raw = self.model([blob])[self.output]                 # (1, 84, 8400) typical

        # Parse — shape is (1, num_classes+4, num_anchors)
        raw = raw[0].T                                        # → (8400, 84)
        boxes_xywh = raw[:, :4]
        scores     = raw[:, 4:]

        class_ids  = scores.argmax(axis=1)
        confidences = scores.max(axis=1)

        keep = confidences >= conf
        if classes is not None:
            keep &= np.isin(class_ids, classes)

        boxes_xywh  = boxes_xywh[keep]
        confidences = confidences[keep]
        class_ids   = class_ids[keep]

        # xywh (normalised to imgsz) → xyxy (pixel coords in original frame)
        x_scale = w0 / sz
        y_scale = h0 / sz

        results_list = []
        for (cx, cy, bw, bh), c, cls in zip(boxes_xywh, confidences, class_ids):
            x1 = int((cx - bw / 2) * x_scale)
            y1 = int((cy - bh / 2) * y_scale)
            x2 = int((cx + bw / 2) * x_scale)
            y2 = int((cy + bh / 2) * y_scale)
            results_list.append(_FakeBox(x1, y1, x2, y2, float(c), int(cls)))

        return [_FakeResult(results_list)]


class _FakeBox:
    """Mimics ultralytics Box object just enough for ModelLoader methods."""
    def __init__(self, x1, y1, x2, y2, conf, cls_id):
        import torch
        self.xyxy = [torch.tensor([x1, y1, x2, y2], dtype=torch.float32)]
        self.conf = [torch.tensor(conf)]
        self.cls  = [torch.tensor(cls_id)]
        self.id   = None   # no tracking ID from raw OV inference


class _FakeResult:
    """Mimics ultralytics Results object."""
    def __init__(self, boxes: list):
        self.boxes = _FakeBoxes(boxes)


class _FakeBoxes:
    def __init__(self, box_list):
        self._boxes = box_list
        # tracking IDs — None means fallback path in detect_persons()
        self.id = None

    def __iter__(self):
        return iter(self._boxes)

    def __len__(self):
        return len(self._boxes)

class ModelLoader:
    """
    Loads person + PPE models. Supports both PyTorch (.pt) and
    OpenVINO (folder with .xml/.bin) formats transparently — just
    point config paths at the openvino folder instead of the .pt file.
    """

    def __init__(self, config):
        self.config = config

        person_path = config["person_model"]
        ppe_path    = config["ppe_model"]

        # Ultralytics handles OpenVINO folders natively via the same YOLO() API.
        # If the path is a directory we pass task= so it doesn't try to infer from extension.
        self.person_model = self._load(person_path, task="detect")
        self.ppe_model    = self._load(ppe_path,    task="detect")

        self.person_conf = config["person_conf"]
        self.ppe_conf    = config["ppe_conf"]

        # Load labels — resolve path relative to project root or ml_pipeline dir
        data_yaml = self._resolve_data_yaml(config)
        with open(data_yaml, "r") as f:
            data = yaml.safe_load(f)
            self.class_names = data.get("names", {})

        # violation classes = anything prefixed with "no_"
        self.violation_classes = {
            id for id, name in self.class_names.items()
            if str(name).startswith("no_")
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _load(path: str, task: str = "detect") -> "YOLO | _OpenVINOModel":
        # Resolve xml path
        xml_path = None
        if os.path.isdir(path):
            xml_files = [f for f in os.listdir(path) if f.endswith(".xml")]
            if xml_files:
                xml_path = os.path.join(path, xml_files[0])
        elif path.endswith(".xml"):
            xml_path = path

        if xml_path:
            print(f"[ModelLoader] Loading OpenVINO model from: {xml_path}")
            return _OpenVINOModel(xml_path)

        print(f"[ModelLoader] Loading PyTorch model from: {path}")
        return YOLO(path)

    @staticmethod
    def _resolve_data_yaml(config: dict) -> str:
        """Find data.yaml — try config key first, then common locations."""
        candidates = [
            config.get("data_yaml", ""),
            "ml_pipeline/data.yaml",
            "data.yaml",
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        raise FileNotFoundError(
            "data.yaml not found. Set 'data_yaml' key in config.yaml."
        )

    # ── Public inference methods ──────────────────────────────────────────────

    def detect_persons(self, frame: np.ndarray) -> list[dict]:
        """
        Returns list of person bounding boxes with stable track IDs:
        [{"bbox": [x1,y1,x2,y2], "conf": 0.92, "track_id": 1}, ...]
        """
        results = self.person_model.track(
            frame, persist=True, conf=self.person_conf,
            classes=[0], verbose=False
        )[0]

        persons = []
        if results.boxes.id is not None:
            ids = results.boxes.id.cpu().numpy().astype(int)
            for box, track_id in zip(results.boxes, ids):
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                persons.append({
                    "bbox": [x1, y1, x2, y2],
                    "conf": float(box.conf[0]),
                    "track_id": int(track_id),
                })
        else:
            # Fallback: no active tracks yet
            for i, box in enumerate(results.boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                persons.append({
                    "bbox": [x1, y1, x2, y2],
                    "conf": float(box.conf[0]),
                    "track_id": -(i + 1),
                })
        return persons

    def detect_all_ppe(self, frame: np.ndarray) -> list[dict]:
        """
        Runs PPE model on the full frame and returns all detections:
        [{"class_id":10, "class_name":"no_hardhat", "conf":0.87,
          "bbox":[x1,y1,x2,y2], "is_violation":True}, ...]
        """
        results = self.ppe_model(frame, conf=self.ppe_conf, verbose=False)[0]
        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            detections.append({
                "class_id":    cls_id,
                "class_name":  self.class_names.get(cls_id, "unknown"),
                "conf":        float(box.conf[0]),
                "bbox":        [x1, y1, x2, y2],
                "is_violation": cls_id in self.violation_classes,
            })
        return detections

    def detect_ppe_in_roi(self, frame: np.ndarray, bbox: list) -> list[dict]:
        """
        Crops person ROI, runs PPE model, returns per-person detections.
        (Kept for backward compatibility; detect_all_ppe is preferred.)
        """
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        pad = 15
        roi = frame[max(0, y1-pad):min(h, y2+pad),
                    max(0, x1-pad):min(w, x2+pad)]
        if roi.size == 0:
            return []
        results = self.ppe_model(roi, conf=self.ppe_conf, verbose=False)[0]
        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            detections.append({
                "class_id":    cls_id,
                "class_name":  self.class_names.get(cls_id, "unknown"),
                "conf":        float(box.conf[0]),
                "is_violation": cls_id in self.violation_classes,
            })
        return detections

    def extract_face_embedding(self, frame: np.ndarray, bbox: list):
        """Optional HOG face embedding — requires face_recognition library."""
        try:
            import face_recognition
        except ImportError:
            return None
        x1, y1, x2, y2 = bbox
        roi = frame[y1:y2, x1:x2]
        rgb_roi = roi[:, :, ::-1]
        face_locations = face_recognition.face_locations(rgb_roi, model="hog")
        if face_locations:
            encodings = face_recognition.face_encodings(rgb_roi, face_locations)
            if encodings:
                return encodings[0].tolist()
        return None