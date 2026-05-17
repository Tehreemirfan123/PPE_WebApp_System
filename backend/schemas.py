"""
Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────
class DetectionStatus(str, Enum):
    open = "open"
    resolved = "resolved"

class UserRole(str, Enum):
    admin = "admin"
    security_officer = "security_officer"


# ─── Auth ─────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None


# ─── User ─────────────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Site Requirement ─────────────────────────────────────────────────────────
class SiteRequirementBase(BaseModel):
    ppe_item: str

class SiteRequirementOut(SiteRequirementBase):
    id: int

    class Config:
        from_attributes = True


# ─── Site ─────────────────────────────────────────────────────────────────────
class SiteCreate(BaseModel):
    name: str
    location: Optional[str] = None
    description: Optional[str] = None
    ppe_requirements: List[str] = []  

class SiteUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    ppe_requirements: Optional[List[str]] = None

class SiteOut(BaseModel):
    id: int
    name: str
    location: Optional[str]
    description: Optional[str]
    is_default: bool
    is_active: bool
    created_at: datetime
    requirements: List[SiteRequirementOut] = []

    class Config:
        from_attributes = True


# ─── Camera ───────────────────────────────────────────────────────────────────
class CameraCreate(BaseModel):
    site_name: str
    camera_name: str
    location: Optional[str] = None
    stream_url: Optional[str] = None

class CameraOut(BaseModel):
    id: int
    site_name: str
    camera_name: str
    location: Optional[str]
    stream_url: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Worker ───────────────────────────────────────────────────────────────────
class WorkerCreate(BaseModel):
    employee_id: str
    full_name: str
    department: Optional[str] = None
    site_name: Optional[str] = None
    face_image_path: Optional[str] = None

class WorkerUpdate(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    site_name: Optional[str] = None
    face_image_path: Optional[str] = None
    is_active: Optional[bool] = None

class WorkerOut(BaseModel):
    employee_id: str
    full_name: str
    department: Optional[str]
    site_name: Optional[str]
    face_image_path: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Detection Event ──────────────────────────────────────────────────────────
class DetectionEventCreate(BaseModel):
    camera_name: Optional[str] = None
    site_name: Optional[str] = None
    employee_id: Optional[str] = None
    detected_by: Optional[str] = None       # e.g. "yolov8n"
    image_path: Optional[str] = None
    confidence_score: Optional[float] = None
    detected_ppe: List[str] = []
    missing_ppe: List[str] = []

class DetectionEventOut(BaseModel):
    id: int
    camera_name: Optional[str]
    site_name: Optional[str]
    employee_id: Optional[str]
    detected_by: Optional[str]
    image_path: Optional[str]
    confidence_score: Optional[float]
    detected_ppe: Optional[List[str]]
    missing_ppe: Optional[List[str]]
    event_status: str
    timestamp: datetime

    class Config:
        from_attributes = True


# ─── Violation ────────────────────────────────────────────────────────────────
class ViolationCreate(BaseModel):
    event_id: int
    employee_id: Optional[str] = None
    site_name: Optional[str] = None
    camera_name: Optional[str] = None
    missing_item: str
    confidence_score: Optional[float] = None

class ViolationOut(BaseModel):
    id: int
    event_id: int
    employee_id: Optional[str]
    worker_name: Optional[str] = None
    site_name: Optional[str]
    camera_name: Optional[str] = None
    missing_item: str
    confidence_score: Optional[float]
    status: str
    resolved_at: Optional[datetime]
    resolved_by: Optional[int]
    timestamp: datetime
    image_path: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Dashboard Stats ──────────────────────────────────────────────────────────
class SiteStat(BaseModel):
    site: str
    count: int

class DashboardStats(BaseModel):
    total_violations: int
    violations_today: int
    open_violations: int
    resolved_violations: int
    by_site: List[SiteStat]
    compliance_rate: float
