"""
CRUD (Create, Read, Update, Delete) helper functions.
Keeps routers thin and business logic centralised.
"""

from datetime import datetime, date, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date

from backend import models, schemas
from backend.auth import hash_password


# ═══════════════════════════════════════════════════════════════════════════════
#  WORKERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_workers(db: Session, skip: int = 0, limit: int = 100) -> List[models.Worker]:
    return db.query(models.Worker).filter(models.Worker.is_active == True).offset(skip).limit(limit).all()


def get_worker(db: Session, worker_id: int) -> Optional[models.Worker]:
    return db.query(models.Worker).filter(models.Worker.id == worker_id).first()


def get_worker_by_employee_id(db: Session, employee_id: str) -> Optional[models.Worker]:
    return db.query(models.Worker).filter(models.Worker.employee_id == employee_id).first()


def create_worker(db: Session, worker: schemas.WorkerCreate) -> models.Worker:
    site_id = None
    if worker.site_name:
        site = db.query(models.Site).filter(models.Site.name == worker.site_name).first()
        site_id = site.id if site else None

    db_worker = models.Worker(
        employee_id=worker.employee_id,
        full_name=worker.full_name,
        department=worker.department,
        site_id=site_id,
        face_image_path=worker.face_image_path
    )
    db.add(db_worker)
    db.commit()
    db.refresh(db_worker)
    return db_worker


def update_worker(db: Session, employee_id: str, updates: schemas.WorkerUpdate) -> Optional[models.Worker]:
    db_worker = get_worker_by_employee_id(db, employee_id)
    if not db_worker:
        return None
    
    data = updates.model_dump(exclude_unset=True)
    if "site_name" in data:
        site_name = data.pop("site_name")
        if site_name:
            site = db.query(models.Site).filter(models.Site.name == site_name).first()
            db_worker.site_id = site.id if site else None
        else:
            db_worker.site_id = None

    for field, value in data.items():
        setattr(db_worker, field, value)
    db_worker.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_worker)
    return db_worker


def delete_worker(db: Session, employee_id: str) -> bool:
    db_worker = get_worker_by_employee_id(db, employee_id)
    if not db_worker:
        return False
    db_worker.is_active = False          # soft delete
    db.commit()
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  SITES
# ═══════════════════════════════════════════════════════════════════════════════

def get_sites(db: Session, skip: int = 0, limit: int = 100) -> List[models.Site]:
    return db.query(models.Site).filter(models.Site.is_active == True).offset(skip).limit(limit).all()


def get_site_by_name(db: Session, name: str) -> Optional[models.Site]:
    return db.query(models.Site).filter(models.Site.name == name).first()


def create_site(db: Session, site: schemas.SiteCreate) -> models.Site:
    db_site = models.Site(
        name=site.name,
        location=site.location,
        description=site.description,
        is_default=False,
    )
    db.add(db_site)
    db.flush()  # get ID before adding requirements
    for item in site.ppe_requirements:
        db.add(models.SiteRequirement(site_id=db_site.id, ppe_item=item.lower()))
    db.commit()
    db.refresh(db_site)
    return db_site


def update_site(db: Session, name: str, updates: schemas.SiteUpdate) -> Optional[models.Site]:
    db_site = get_site_by_name(db, name)
    if not db_site or db_site.is_default:
        return None
    for field in ("name", "location", "description"):
        val = getattr(updates, field, None)
        if val is not None:
            setattr(db_site, field, val)
    if updates.ppe_requirements is not None:
        db.query(models.SiteRequirement).filter_by(site_id=db_site.id).delete()
        for item in updates.ppe_requirements:
            db.add(models.SiteRequirement(site_id=db_site.id, ppe_item=item.lower()))
    db.commit()
    db.refresh(db_site)
    return db_site


def delete_site(db: Session, name: str) -> bool:
    db_site = get_site_by_name(db, name)
    if not db_site or db_site.is_default:
        return False
    db_site.is_active = False
    db.commit()
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  CAMERAS
# ═══════════════════════════════════════════════════════════════════════════════

def get_cameras(db: Session, site_id: Optional[int] = None) -> List[models.Camera]:
    q = db.query(models.Camera).filter(models.Camera.is_active == True)
    if site_id:
        q = q.filter(models.Camera.site_id == site_id)
    return q.all()


def create_camera(db: Session, camera: schemas.CameraCreate) -> models.Camera:
    db_camera = models.Camera(**camera.model_dump())
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera


# ═══════════════════════════════════════════════════════════════════════════════
#  DETECTION EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

def create_detection_event(db: Session, event: schemas.DetectionEventCreate) -> models.DetectionEvent:
    data = event.model_dump(exclude={"camera_name", "site_name", "employee_id"})
    
    if event.camera_name:
        cam = db.query(models.Camera).filter(models.Camera.camera_name == event.camera_name).first()
        data["camera_id"] = cam.id if cam else None
    if event.site_name:
        site = db.query(models.Site).filter(models.Site.name == event.site_name).first()
        data["site_id"] = site.id if site else None
    if event.employee_id:
        worker = get_worker_by_employee_id(db, event.employee_id)
        data["worker_id"] = worker.id if worker else None

    db_event = models.DetectionEvent(**data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def get_detection_events(
    db: Session,
    site_name: Optional[str] = None,
    camera_name: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[models.DetectionEvent]:
    q = db.query(models.DetectionEvent)
    if site_name:
        site = db.query(models.Site).filter(models.Site.name == site_name).first()
        q = q.filter(models.DetectionEvent.site_id == (site.id if site else -1))
    if camera_name:
        cam = db.query(models.Camera).filter(models.Camera.camera_name == camera_name).first()
        q = q.filter(models.DetectionEvent.camera_id == (cam.id if cam else -1))
    if status:
        q = q.filter(models.DetectionEvent.event_status == status)
    return q.order_by(models.DetectionEvent.timestamp.desc()).offset(skip).limit(limit).all()


# ═══════════════════════════════════════════════════════════════════════════════
#  VIOLATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_violation(db: Session, violation: schemas.ViolationCreate) -> models.Violation:
    data = violation.model_dump(exclude={"employee_id", "site_name", "camera_name"})

    if violation.employee_id:
        worker = get_worker_by_employee_id(db, violation.employee_id)
        data["worker_id"] = worker.id if worker else None
    if violation.site_name:
        site = db.query(models.Site).filter(models.Site.name == violation.site_name).first()
        data["site_id"] = site.id if site else None
    if violation.camera_name:
        cam = db.query(models.Camera).filter(models.Camera.camera_name == violation.camera_name).first()
        data["camera_id"] = cam.id if cam else None

    db_violation = models.Violation(**data)
    db.add(db_violation)
    db.commit()
    db.refresh(db_violation)
    return db_violation


def get_violations(
    db: Session,
    site_name: Optional[str] = None,
    camera_name: Optional[str] = None,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[models.Violation]:
    q = db.query(models.Violation)
    if site_name:
        site = db.query(models.Site).filter(models.Site.name == site_name).first()
        q = q.filter(models.Violation.site_id == (site.id if site else -1))
    if camera_name:
        cam = db.query(models.Camera).filter(models.Camera.camera_name == camera_name).first()
        q = q.filter(models.Violation.camera_id == (cam.id if cam else -1))
    if employee_id:
        worker = get_worker_by_employee_id(db, employee_id)
        q = q.filter(models.Violation.worker_id == (worker.id if worker else -1))
    if status:
        q = q.filter(models.Violation.status == status)
    if date_from:
        q = q.filter(cast(models.Violation.timestamp, Date) >= date_from)
    if date_to:
        q = q.filter(cast(models.Violation.timestamp, Date) <= date_to)
    return q.order_by(models.Violation.timestamp.desc()).offset(skip).limit(limit).all()


def resolve_violation(db: Session, violation_id: int, resolved_by_user_id: int) -> Optional[models.Violation]:
    v = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not v:
        return None
    v.status = "resolved"
    v.resolved_at = datetime.now(timezone.utc)
    v.resolved_by = resolved_by_user_id
    db.commit()
    db.refresh(v)
    return v


# ═══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_dashboard_stats(db: Session) -> schemas.DashboardStats:
    total = db.query(func.count(models.Violation.id)).scalar() or 0
    open_count = db.query(func.count(models.Violation.id)).filter(models.Violation.status == "open").scalar() or 0
    resolved_count = total - open_count

    today = datetime.now(timezone.utc).date()
    today_count = (
        db.query(func.count(models.Violation.id))
        .filter(cast(models.Violation.timestamp, Date) == today)
        .scalar()
        or 0
    )

    by_site_rows = (
        db.query(models.Site.name, func.count(models.Violation.id))
        .outerjoin(models.Violation, models.Site.id == models.Violation.site_id)
        .group_by(models.Site.name)
        .order_by(func.count(models.Violation.id).desc())
        .all()
    )
    by_site = [schemas.SiteStat(site=row[0], count=row[1]) for row in by_site_rows]

    # Compliance rate = resolved / total (avoid div by zero)
    compliance = round(resolved_count / total, 4) if total > 0 else 1.0

    return schemas.DashboardStats(
        total_violations=total,
        violations_today=today_count,
        open_violations=open_count,
        resolved_violations=resolved_count,
        by_site=by_site,
        compliance_rate=compliance,
    )
