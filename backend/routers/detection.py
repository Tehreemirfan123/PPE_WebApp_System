"""
Router: POST /detection-event/  POST /violation/
These are called by the ML pipeline to log events.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import schemas, crud, models
from backend.auth import get_current_user

router = APIRouter(tags=["Detection"])


@router.post("/detection-event/", response_model=schemas.DetectionEventOut, status_code=201)
def create_detection_event(
    event: schemas.DetectionEventCreate,
    db: Session = Depends(get_db),
    # ML pipeline can call this with a valid token (admin or officer)
    current_user: models.User = Depends(get_current_user),
):
    """
    Called by the ML pipeline when a violation is detected.
    Only saves events with at least one missing PPE item.
    """
    if not event.missing_ppe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Detection event must have at least one missing PPE item."
        )
    return crud.create_detection_event(db, event)


@router.post("/violation/", response_model=schemas.ViolationOut, status_code=201)
def create_violation(
    violation: schemas.ViolationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a single violation record (one per missing PPE item)."""
    return crud.create_violation(db, violation)


@router.get("/detection-events/", response_model=List[schemas.DetectionEventOut])
def list_detection_events(
    site_name: Optional[str] = None,
    camera_name: Optional[str] = None,
    event_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_detection_events(
        db, site_name=site_name, camera_name=camera_name,
        status=event_status, skip=skip, limit=limit
    )
