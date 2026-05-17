import time
import hashlib
from collections import defaultdict

# From your dataset mappings in data.yaml
CONFLICT_PAIRS = {
    # (compliant_id, violation_id)
    (0, 6),   # earmuffs vs no_earmuffs
    (1, 7),   # face_mask vs no_face_mask
    (2, 8),   # gloves vs no_gloves
    (3, 9),   # goggles vs no_goggles
    (4, 10),  # hardhat vs no_hardhat
    (5, 11),  # labcoat vs no_labcoat
    (14, 12), # safety_shoes vs no_safety_shoes
    (15, 13)  # safety_vest vs no_safety_vest
}

class ComplianceLogic:
    def __init__(self, config):
        self.temporal_frames = config['temporal_frames']
        self.alert_conf = config['alert_conf']
        self.cooldown_seconds = config['cooldown_seconds']
        self.camera_name = config['camera_name']
        self.site_name = config['site_name']
        
        # track_id -> {missing_item: frame_count}
        self._temporal_buffer: dict = defaultdict(lambda: defaultdict(int))
        
        # Cooldown buffer to suppress duplicate alerts
        # Key: (camera_name, site_name, track_id, missing_item)
        # Value: timestamp of last alert
        self._cooldown_buffer: dict = {}
        
        # Track saved violations to avoid duplicate images
        # Key: hash of (track_id, violation_set, site_name)
        # Value: timestamp when first saved
        self._saved_violations_cache: dict = {}
        
        # Grace period: within this time, don't save same violation again
        self._image_save_grace_period = 30  # seconds
        
        # Site Inference state
        self._site_votes = defaultdict(int)
        self._inferred_site = None

    def infer_site(self, detections: list[dict]):
        """
        Incrementally votes for a site type based on high-confidence unique PPE signifiers.
        If no unique signifiers are detected, it preserves the configured site to prevent false down-grades.
        """
        if self._inferred_site:
            return self._inferred_site
            
        db_to_yolo = {
            "helmet": "hardhat",
            "boots": "safety_shoes",
            "lab_coat": "labcoat"
        }
        
        found_classes = {d["class_name"] for d in detections}
        if not found_classes:
            return None
            
        # Vote based on high-confidence positive signifiers
        if "labcoat" in found_classes or "goggles" in found_classes or "face_mask" in found_classes:
            self._site_votes["Chemical Lab"] += 5
        elif "earmuffs" in found_classes:
            self._site_votes["Factory"] += 5
        elif "safety_shoes" in found_classes:
            self._site_votes["Construction Site"] += 5
        elif "hardhat" in found_classes and "safety_vest" in found_classes:
            # Could be Factory, Construction Site, or Warehouse.
            self._site_votes["Warehouse"] += 1
        
        # If any site has > 50 votes (roughly 2-5 seconds of consistent detection), lock it in
        for site, votes in self._site_votes.items():
            if votes > 50:
                self._inferred_site = site
                print(f"[INFO] Inferred Site Type: {site}")
                return site
        
        return None

    def resolve_conflicts(self, detections: list[dict]) -> list[dict]:
        """If both a PPE class and its 'no' class are detected, keep the higher-confidence one."""
        class_conf = {d["class_id"]: d for d in detections}
        to_remove = set()
        for comp_id, viol_id in CONFLICT_PAIRS:
            if comp_id in class_conf and viol_id in class_conf:
                if class_conf[comp_id]["conf"] >= class_conf[viol_id]["conf"]:
                    to_remove.add(viol_id)
                else:
                    to_remove.add(comp_id)
        return [d for d in detections if d["class_id"] not in to_remove]

    def evaluate_policy(self, detections: list[dict], required_ppe: list[str]) -> list[str]:
        """
        Returns list of missing PPE items (violations) based on site policy.
        required_ppe: e.g. ["hardhat", "safety_vest", "gloves"]
        """
        # Map database taxonomy to YOLO taxonomy
        db_to_yolo = {
            "helmet": "hardhat",
            "boots": "safety_shoes",
            "lab_coat": "labcoat"
        }
        
        translated_required = [db_to_yolo.get(item, item) for item in required_ppe]
        
        violation_names = {d["class_name"] for d in detections if d["is_violation"] and d["conf"] >= self.alert_conf}
        missing = []
        for item in translated_required:
            # Look for the exact "no_item" equivalent based on taxonomy
            violation_str = f"no_{item}"
            if violation_str in violation_names:
                missing.append(violation_str)
        return missing

    def update_temporal(self, track_id: int, missing_items: list[str]) -> list[str]:
        """
        Returns only the violations that have persisted for >= temporal_frames.
        Resets counter for items that are now compliant.
        """
        buf = self._temporal_buffer[track_id]
        
        # Increment for current violations
        for item in missing_items:
            buf[item] += 1
            
        # Reset for items no longer violating
        for item in list(buf.keys()):
            if item not in missing_items:
                buf[item] = 0
                
        # Return only confirmed violations
        return [item for item, count in buf.items() if count >= self.temporal_frames]

    def apply_cooldown(self, track_id: int, confirmed_missing_items: list[str]) -> list[str]:
        """
        Filters the confirmed missing items to suppress duplicates based on cooldown rule.
        """
        current_time = time.time()
        final_violations_to_log = []

        for item in confirmed_missing_items:
            key = (self.camera_name, self.site_name, track_id, item)
            
            if key in self._cooldown_buffer:
                time_since_last = current_time - self._cooldown_buffer[key]
                if time_since_last < self.cooldown_seconds:
                    # Still in cooldown, suppress this log
                    continue
            
            # If not in cooldown buffer, or cooldown expired, we accept it
            self._cooldown_buffer[key] = current_time
            final_violations_to_log.append(item)
            
        return final_violations_to_log

    def should_save_violation_image(self, missing_items: list[str]) -> bool:
        """
        Determines if a violation image should be saved based on deduplication logic.
        
        Returns True only if:
        1. This is a NEW violation set for the site (never seen before), OR
        2. The grace period has expired since the last time this exact violation set was saved.
        
        This prevents saving every frame of a continuous violation.
        """
        if not missing_items:
            return False
            
        # Create a unique hash of the violation set
        violation_key = frozenset(missing_items)
        cache_key = (self.site_name, violation_key)
        
        current_time = time.time()
        
        # Clean up old entries
        if cache_key in self._saved_violations_cache:
            time_since_last = current_time - self._saved_violations_cache[cache_key]
            if time_since_last < self._image_save_grace_period:
                # Grace period not expired - skip saving
                return False
        
        # Either new or grace period expired - save image
        self._saved_violations_cache[cache_key] = current_time
        return True
    
    def get_saved_violations_stats(self) -> dict:
        """
        Returns statistics about saved violations for monitoring.
        """
        return {
            "total_unique_violations_tracked": len(self._saved_violations_cache),
            "active_cooldowns": len(self._cooldown_buffer),
            "grace_period_seconds": self._image_save_grace_period,
            "temporal_frames_required": self.temporal_frames,
            "cooldown_seconds": self.cooldown_seconds,
        }
