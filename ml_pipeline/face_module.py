"""
face_module.py  —  Real-time face recognition for the PPE ML pipeline.

Strategy
--------
* At registration time  : DeepFace extracts a 512-d ArcFace embedding from the
                          worker's uploaded photo and stores it in the `workers`
                          table (face_embedding column, pgvector).
* At inference time     : For every face detected in a frame we extract its
                          embedding with DeepFace, then do a single SQL query
                          (cosine similarity via pgvector) to find the closest
                          worker.  No folder scanning, no per-frame DeepFace.find().

This keeps recognition fast enough for real-time use on CPU.
"""

import cv2
import numpy as np
from deepface import DeepFace

# ── Haar cascade for fast face detection ──────────────────────────────────────
import cv2 as _cv2
_cascade_path = _cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_face_cascade = _cv2.CascadeClassifier(_cascade_path)

# ── Recognition hyper-parameters ─────────────────────────────────────────────
COSINE_THRESHOLD = 0.40   # distances above this → Unknown Worker
MARGIN_MIN       = 0.05   # top-2 must differ by at least this (ambiguity check)
MODEL_NAME       = "ArcFace"
EMBEDDING_DIM    = 512


# ─────────────────────────────────────────────────────────────────────────────
# Embedding helpers
# ─────────────────────────────────────────────────────────────────────────────

def extract_embedding(img_rgb: np.ndarray) -> np.ndarray | None:
    """
    Extract a 512-d ArcFace embedding from an RGB image crop.
    Returns a numpy array of shape (512,), or None on failure.
    """
    try:
        result = DeepFace.represent(
            img_path=img_rgb,
            model_name=MODEL_NAME,
            enforce_detection=False,
            detector_backend="skip",   # we already cropped the face
        )
        if result and len(result) > 0:
            vec = np.array(result[0]["embedding"], dtype=np.float32)
            # L2-normalise so cosine distance == 1 - dot-product
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            return vec
    except Exception as exc:
        print(f"[FaceModule] Embedding error: {exc}")
    return None


def embedding_for_file(image_path: str) -> np.ndarray | None:
    """
    Extract embedding directly from a file path (used at registration time).
    """
    try:
        result = DeepFace.represent(
            img_path=image_path,
            model_name=MODEL_NAME,
            enforce_detection=False,
        )
        if result and len(result) > 0:
            vec = np.array(result[0]["embedding"], dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            return vec
    except Exception as exc:
        print(f"[FaceModule] File embedding error: {exc}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DB-backed recognition cache
# ─────────────────────────────────────────────────────────────────────────────

class FaceRecognizer:
    """
    Loads all worker embeddings from the database once at startup, then
    does in-process cosine nearest-neighbour search on every frame.

    Call refresh() to pick up newly registered workers without restarting
    the pipeline.
    """

    def __init__(self, db_session_factory):
        """
        Parameters
        ----------
        db_session_factory : callable
            A zero-argument callable that returns a SQLAlchemy Session,
            e.g. the `SessionLocal` factory from backend.database.
        """
        self._factory = db_session_factory
        self._embeddings: list[np.ndarray] = []
        self._names:      list[str]        = []
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self):
        """Reload all embeddings from DB. Call after new workers are added."""
        self._embeddings = []
        self._names      = []
        try:
            db = self._factory()
            from backend.models import Worker
            workers = db.query(Worker).filter(Worker.face_embedding.isnot(None)).all()
            for w in workers:
                raw = w.face_embedding          # pgvector returns list[float]
                if raw is None:
                    continue
                vec = np.array(raw, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec /= norm
                self._embeddings.append(vec)
                self._names.append(f"{w.first_name} {w.last_name}")
            db.close()
            print(f"[FaceModule] Loaded {len(self._names)} worker embeddings from DB.")
        except Exception as exc:
            print(f"[FaceModule] Could not load embeddings from DB: {exc}")

    # ------------------------------------------------------------------
    def identify(self, face_embedding: np.ndarray) -> str:
        """
        Compare a query embedding against all known workers.
        Returns worker full name, or 'Unknown Worker'.
        """
        if not self._embeddings or face_embedding is None:
            return "Unknown Worker"

        # Cosine distances (1 - dot-product for unit vectors)
        dots = np.array([np.dot(face_embedding, e) for e in self._embeddings])
        distances = 1.0 - dots          # lower = more similar

        sorted_idx = np.argsort(distances)
        best_idx  = sorted_idx[0]
        best_dist = distances[best_idx]

        if best_dist > COSINE_THRESHOLD:
            return "Unknown Worker"

        # Ambiguity check: top-2 matches must be clearly separated
        if len(sorted_idx) > 1:
            second_dist = distances[sorted_idx[1]]
            if (second_dist - best_dist) < MARGIN_MIN:
                return "Unknown Worker"

        return self._names[best_idx]


# ─────────────────────────────────────────────────────────────────────────────
# Frame-level face processing
# ─────────────────────────────────────────────────────────────────────────────

def detect_faces(rgb_img: np.ndarray) -> list[tuple[int, int, int, int]]:
    """
    Detect face bounding boxes in an RGB image using the Haar cascade.
    Returns a list of (top, right, bottom, left) tuples  — same convention
    as face_recognition so the rest of the codebase stays familiar.
    """
    gray = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2GRAY)
    faces = _face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=6,
        minSize=(60, 60),
    )
    locations = []
    for (x, y, w, h) in faces:
        locations.append((y, x + w, y + h, x))   # (top, right, bottom, left)
    return locations


def process_faces(
    rgb_img: np.ndarray,
    recognizer: FaceRecognizer,
) -> tuple[list[tuple], list[str]]:
    """
    Detect and identify all faces in an RGB frame.

    Parameters
    ----------
    rgb_img    : np.ndarray  HxWx3 RGB image
    recognizer : FaceRecognizer  pre-loaded instance

    Returns
    -------
    face_locations : list of (top, right, bottom, left)
    detected_names : list of str  (worker name or 'Unknown Worker')
    """
    face_locations = detect_faces(rgb_img)
    detected_names = []

    for (top, right, bottom, left) in face_locations:
        face_crop = rgb_img[top:bottom, left:right]
        if face_crop.size == 0:
            detected_names.append("Unknown Worker")
            continue

        embedding = extract_embedding(face_crop)
        name = recognizer.identify(embedding)
        detected_names.append(name)

    return face_locations, detected_names


# ─────────────────────────────────────────────────────────────────────────────
# Utility: match a YOLO person bbox to the nearest detected face
# ─────────────────────────────────────────────────────────────────────────────

def match_person_to_face(
    person_bbox: tuple[int, int, int, int],
    face_locations: list[tuple[int, int, int, int]],
    face_names: list[str],
    max_distance_px: int = 200,
) -> str:
    """
    Given a YOLO person bounding box (x1,y1,x2,y2) and a list of detected
    faces, return the name of the face whose centre is closest to the person's
    upper-body centre, within max_distance_px pixels.

    Returns 'Unknown Worker' if no close face is found.
    """
    if not face_locations:
        return "Unknown Worker"

    px1, py1, px2, py2 = person_bbox
    # Use upper-body centre (top third of person box) to stay near the head
    p_cx = (px1 + px2) // 2
    p_cy = py1 + (py2 - py1) // 4

    best_name = "Unknown Worker"
    best_dist = float("inf")

    for (top, right, bottom, left), name in zip(face_locations, face_names):
        f_cx = (left + right) // 2
        f_cy = (top + bottom) // 2
        dist = ((p_cx - f_cx) ** 2 + (p_cy - f_cy) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_name = name

    return best_name if best_dist <= max_distance_px else "Unknown Worker"