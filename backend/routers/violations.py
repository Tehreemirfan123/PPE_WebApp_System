"""
Router: GET /violations/   PUT /violations/{id}/resolve
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import schemas, crud, models
from backend.auth import require_officer_or_admin, require_security_officer

router = APIRouter(prefix="/violations", tags=["Violations"])


@router.get("/", response_model=List[schemas.ViolationOut])
def list_violations(
    site_name: Optional[str] = None,
    camera_name: Optional[str] = None,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_officer_or_admin),
):
    violations = crud.get_violations(
        db,
        site_name=site_name,
        camera_name=camera_name,
        employee_id=employee_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )

    # Enrich with joined display names
    results = []
    for v in violations:
        event = db.query(models.DetectionEvent).filter(models.DetectionEvent.id == v.event_id).first()
        out = schemas.ViolationOut.model_validate(v)
        out.image_path = event.image_path if event else None
        results.append(out)
    return results


@router.put("/{violation_id}/resolve", response_model=schemas.ViolationOut)
def resolve_violation(
    violation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_security_officer),
):
    v = crud.resolve_violation(db, violation_id, resolved_by_user_id=current_user.id)
    if not v:
        raise HTTPException(status_code=404, detail="Violation not found")
    return v
