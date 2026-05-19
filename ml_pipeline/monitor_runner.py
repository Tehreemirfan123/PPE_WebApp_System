"""
monitor_runner.py
─────────────────
Self-contained inference engine for the Streamlit Live Monitor page.

Runs in the SAME process as Streamlit (no subprocess), processing frames
one at a time and yielding annotated frames + violation records back to
the page via a generator.  The page controls start/stop via a flag in
st.session_state, so no threads or queues are needed.

Usage (from live_feed.py):
    from ml_pipeline.monitor_runner import MonitorRunner
    runner = MonitorRunner(config, source)
    for frame_rgb, violations in runner.process():
        # frame_rgb  → annotated BGR→RGB numpy array for st.image()
        # violations → list of dicts logged this iteration
        ...
"""

import cv2
import yaml
import os
import sys
import time
import numpy as np
from datetime import datetime

# Allow imports from project root when called from frontend/
# Ensure project root is on the path regardless of where Streamlit is launched from
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ml_pipeline.model_loader import ModelLoader
from ml_pipeline.compliance   import ComplianceLogic


# Absolute path to the ml_pipeline/ directory itself
_ML_DIR      = os.path.dirname(os.path.abspath(__file__))
# Absolute path to the project root (one level up from ml_pipeline/)
_PROJECT_ROOT = os.path.dirname(_ML_DIR)


def _resolve(relative_path: str) -> str:
    """
    Resolve a config path to absolute.
    For OpenVINO model folders, resolves to the .xml file inside.
    """
    if os.path.isabs(relative_path):
        candidate = relative_path
    else:
        candidate = os.path.join(_PROJECT_ROOT, relative_path)
        if not os.path.exists(candidate):
            candidate = os.path.join(_ML_DIR, relative_path)

    # If it's a directory, look for the .xml file inside it
    if os.path.isdir(candidate):
        xml_files = [f for f in os.listdir(candidate) if f.endswith(".xml")]
        if xml_files:
            return os.path.join(candidate, xml_files[0])

    return candidate


def _load_config(path: str = None) -> dict:
    if path is None:
        path = os.path.join(_ML_DIR, "config.yaml")
    with open(path) as f:
        config = yaml.safe_load(f)

    # Resolve all path values to absolute so nothing depends on cwd
    for key in ("person_model", "ppe_model", "data_yaml",
                "saved_violations_dir"):
        if key in config and config[key]:
            config[key] = _resolve(str(config[key]))

    return config

class MonitorRunner:
    """
    Wraps the full ML pipeline for use inside Streamlit.

    Parameters
    ----------
    source : int | str
        0 / 1 → webcam index
        "path/to/video.mp4" → uploaded or local video file
    config_path : str
        Path to config.yaml (default: ml_pipeline/config.yaml)
    site_name : str | None
        Override site name from config (e.g. chosen in UI dropdown).
    log_to_backend : bool
        Whether to POST violations to the FastAPI backend.
        Set False when backend is not running (pure offline mode).
    """

    def __init__(
        self,
        source,
        config_path: str = None,                          
        site_name: str | None = None,
        log_to_backend: bool = True,
    ):
        self.config = _load_config(config_path)        
        if site_name:
            self.config["site_name"] = site_name

        self.source          = source
        self.log_to_backend  = log_to_backend
        self.violation_log   = []   # accumulated list of dicts for CSV

        # Models + compliance
        self.models     = ModelLoader(self.config)
        self.compliance = ComplianceLogic(self.config)

        # Optional backend client
        self._client = None
        self._required_ppe = []
        if self.log_to_backend:
            self._init_backend()

    # ── Backend setup ─────────────────────────────────────────────────────────

    def _init_backend(self):
        try:
            from ml_pipeline.backend_client import BackendClient
            client = BackendClient(self.config)
            if client.authenticate():
                self._client       = client
                self._required_ppe = client.get_required_ppe(
                    self.config["site_name"]
                )
            else:
                print("[MonitorRunner] Backend auth failed — running offline.")
        except Exception as e:
            print(f"[MonitorRunner] Backend unavailable ({e}) — running offline.")

    # ── Main generator ────────────────────────────────────────────────────────

    def process(self):
        """
        Generator — yields (frame_rgb, new_violations) for every frame.

        frame_rgb       → H×W×3 uint8 RGB array ready for st.image()
        new_violations  → list of violation dicts logged on this frame
                          (empty list on most frames)

        The caller breaks the loop when the user clicks Stop.
        """
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {self.source}")

        skip_frames          = self.config.get("skip_frames", 4)
        frame_count          = 0
        cached_draw_actions  = []

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    # Loop video files; stop on webcam disconnect
                    if isinstance(self.source, str):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    break

                frame_count += 1
                should_process = (frame_count % skip_frames == 0) or (frame_count == 1)
                new_violations = []

                if should_process:
                    persons  = self.models.detect_persons(frame)
                    all_ppe  = self.models.detect_all_ppe(frame)

                    # Dynamic site inference
                    if self.config.get("auto_detect_site", True) and all_ppe:
                        inferred = self.compliance.infer_site(all_ppe)
                        if inferred and inferred != self.config["site_name"]:
                            self.config["site_name"] = inferred
                            if self._client:
                                self._client.config["site_name"] = inferred
                            self.compliance.site_name = inferred
                            self._required_ppe = (
                                self._client.get_required_ppe(inferred)
                                if self._client else []
                            )

                    # Map PPE → persons by overlap
                    person_detections = {p["track_id"]: [] for p in persons}
                    for ppe in all_ppe:
                        bx1, by1, bx2, by2 = ppe["bbox"]
                        ppe_area = max((bx2 - bx1) * (by2 - by1), 1)
                        best_id, best_ovlp = None, 0.0
                        for person in persons:
                            px1, py1, px2, py2 = person["bbox"]
                            ix1 = max(px1, bx1); iy1 = max(py1, by1)
                            ix2 = min(px2, bx2); iy2 = min(py2, by2)
                            if ix2 > ix1 and iy2 > iy1:
                                ovlp = ((ix2-ix1)*(iy2-iy1)) / ppe_area
                                if ovlp > best_ovlp:
                                    best_ovlp = ovlp
                                    best_id   = person["track_id"]
                        if best_id is not None and best_ovlp > 0.3:
                            person_detections[best_id].append(ppe)

                    # Per-person compliance + draw
                    cached_draw_actions  = []
                    frame_violations     = []
                    highest_conf         = 0.0

                    for person in persons:
                        tid  = person["track_id"]
                        bbox = person["bbox"]
                        highest_conf = max(highest_conf, person["conf"])

                        detections = self.compliance.resolve_conflicts(
                            person_detections[tid]
                        )
                        missing   = self.compliance.evaluate_policy(
                            detections, self._required_ppe
                        )
                        confirmed = self.compliance.update_temporal(tid, missing)
                        final     = self.compliance.apply_cooldown(tid, confirmed)

                        color = (0, 0, 255) if missing else (0, 255, 0)
                        x1, y1, x2, y2 = bbox
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                        label = None
                        if missing:
                            label = f"ID:{tid} " + ", ".join(missing[:2])
                            cv2.putText(frame, label, (x1, y1 - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                                        (0, 0, 255), 2)
                            if final:
                                for v in final:
                                    frame_violations.append((tid, v))

                        cached_draw_actions.append({
                            "bbox": (x1, y1, x2, y2),
                            "color": color,
                            "label": label,
                        })

                    # Log to backend + build violation records
                    if frame_violations:
                        should_save = self.compliance.should_save_violation_image(
                            [item for _, item in frame_violations]
                        )
                        if self._client:
                            self._client.log_violation(
                                frame, [item for _, item in frame_violations],
                                highest_conf,
                                should_save_image=should_save,
                            )

                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        for tid, v in frame_violations:
                            record = {
                                "timestamp":   ts,
                                "site":        self.config["site_name"],
                                "camera":      self.config.get("camera_name", ""),
                                "track_id":    tid,
                                "missing_ppe": v,
                                "confidence":  round(highest_conf, 3),
                            }
                            self.violation_log.append(record)
                            new_violations.append(record)

                else:
                    # Skipped frame — replay cached annotations
                    for action in cached_draw_actions:
                        x1, y1, x2, y2 = action["bbox"]
                        cv2.rectangle(frame, (x1, y1), (x2, y2), action["color"], 2)
                        if action["label"]:
                            cv2.putText(frame, action["label"], (x1, y1 - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                                        (0, 0, 255), 2)

                # HUD overlay
                cv2.putText(
                    frame,
                    f"Frame {frame_count} | Violations: {len(self.violation_log)}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2,
                )

                # Resize for display (max 960 wide)
                h, w = frame.shape[:2]
                if w > 960:
                    scale = 960 / w
                    frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

                yield cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), new_violations

        finally:
            cap.release()

    # ── CSV helper ────────────────────────────────────────────────────────────

    def get_csv_bytes(self) -> bytes:
        """Return the accumulated violation log as UTF-8 CSV bytes."""
        import csv
        import io

        if not self.violation_log:
            return b"timestamp,site,camera,track_id,missing_ppe,confidence\n"

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=self.violation_log[0].keys())
        writer.writeheader()
        writer.writerows(self.violation_log)
        return buf.getvalue().encode("utf-8")