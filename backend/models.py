"""
SQLAlchemy ORM models for the PPE Detection System.
Maps to the tables defined in 001_init_schema.sql.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, Numeric,
    TIMESTAMP, ARRAY, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import enum

from backend.database import Base


# ─── Enums ────────────────────────────────────────────────────────────────────
class DetectionStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class UserRole(str, enum.Enum):
    admin = "admin"
    security_officer = "security_officer"


# ─── User ─────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    full_name       = Column(String(255), nullable=False)
    hashed_password = Column(Text, nullable=False)
    role            = Column(SAEnum("admin", "security_officer", name="user_role_enum"), nullable=False)
    is_active       = Column(Boolean, default=True, nullable=False)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    resolved_violations = relationship("Violation", back_populates="resolver")


# ─── Site ─────────────────────────────────────────────────────────────────────
class Site(Base):
    __tablename__ = "sites"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(255), unique=True, nullable=False)
    location    = Column(String(500))
    description = Column(Text)
    is_default  = Column(Boolean, default=False, nullable=False)
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())

    requirements       = relationship("SiteRequirement", back_populates="site", cascade="all, delete-orphan")
    cameras            = relationship("Camera", back_populates="site")
    workers            = relationship("Worker", back_populates="site")
    detection_events   = relationship("DetectionEvent", back_populates="site")
    violations         = relationship("Violation", back_populates="site")


# ─── SiteRequirement ──────────────────────────────────────────────────────────
class SiteRequirement(Base):
    __tablename__ = "site_requirements"

    id       = Column(Integer, primary_key=True, index=True)
    site_id  = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    ppe_item = Column(String(100), nullable=False)

    site = relationship("Site", back_populates="requirements")


# ─── Camera ───────────────────────────────────────────────────────────────────
class Camera(Base):
    __tablename__ = "cameras"

    id          = Column(Integer, primary_key=True, index=True)
    site_id     = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    camera_name = Column(String(255), nullable=False)
    location    = Column(String(500))
    stream_url  = Column(String(500))
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())

    site             = relationship("Site", back_populates="cameras")
    detection_events = relationship("DetectionEvent", back_populates="camera")
    violations       = relationship("Violation", back_populates="camera")


# ─── Worker ───────────────────────────────────────────────────────────────────
class Worker(Base):
    __tablename__ = "workers"

    id              = Column(Integer, primary_key=True, index=True)
    employee_id     = Column(String(100), unique=True, nullable=False, index=True)
    full_name       = Column(String(255), nullable=False)
    department      = Column(String(255))
    site_id         = Column(Integer, ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    face_image_path = Column(Text)
    face_embedding  = Column(Vector(512))       # written by ML pipeline
    is_active       = Column(Boolean, default=True, nullable=False)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at      = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    site             = relationship("Site", back_populates="workers")
    detection_events = relationship("DetectionEvent", back_populates="worker")
    violations       = relationship("Violation", back_populates="worker")

    @property
    def site_name(self):
        return self.site.name if self.site else None


# ─── DetectionEvent ───────────────────────────────────────────────────────────
class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id               = Column(Integer, primary_key=True, index=True)
    camera_id        = Column(Integer, ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    site_id          = Column(Integer, ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    worker_id        = Column(Integer, ForeignKey("workers.id", ondelete="SET NULL"), nullable=True)
    detected_by      = Column(String(255))        # YOLO model version
    image_path       = Column(Text)               # saved violation frame
    confidence_score = Column(Numeric(5, 4))
    detected_ppe     = Column(ARRAY(String))      # items detected
    missing_ppe      = Column(ARRAY(String))      # items missing
    event_status     = Column(SAEnum("open", "resolved", name="detection_status"), default="open", nullable=False)
    timestamp        = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)

    camera     = relationship("Camera", back_populates="detection_events")
    site       = relationship("Site", back_populates="detection_events")
    worker     = relationship("Worker", back_populates="detection_events")
    violations = relationship("Violation", back_populates="event", cascade="all, delete-orphan")

    @property
    def camera_name(self):
        return self.camera.camera_name if self.camera else None

    @property
    def site_name(self):
        return self.site.name if self.site else None

    @property
    def employee_id(self):
        return self.worker.employee_id if self.worker else None


# ─── Violation ────────────────────────────────────────────────────────────────
class Violation(Base):
    __tablename__ = "violations"

    id               = Column(Integer, primary_key=True, index=True)
    event_id         = Column(Integer, ForeignKey("detection_events.id", ondelete="CASCADE"), nullable=False)
    worker_id        = Column(Integer, ForeignKey("workers.id", ondelete="SET NULL"), nullable=True)
    site_id          = Column(Integer, ForeignKey("sites.id", ondelete="SET NULL"), nullable=True)
    camera_id        = Column(Integer, ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    missing_item     = Column(String(100), nullable=False)
    confidence_score = Column(Numeric(5, 4))
    status           = Column(SAEnum("open", "resolved", name="detection_status"), default="open", nullable=False)
    resolved_at      = Column(TIMESTAMP(timezone=True), nullable=True)
    resolved_by      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    timestamp        = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)

    event    = relationship("DetectionEvent", back_populates="violations")
    worker   = relationship("Worker", back_populates="violations")
    site     = relationship("Site", back_populates="violations")
    camera   = relationship("Camera", back_populates="violations")
    resolver = relationship("User", back_populates="resolved_violations")

    @property
    def employee_id(self):
        return self.worker.employee_id if self.worker else None

    @property
    def worker_name(self):
        return self.worker.full_name if self.worker else None

    @property
    def site_name(self):
        return self.site.name if self.site else None

    @property
    def camera_name(self):
        return self.camera.camera_name if self.camera else None
