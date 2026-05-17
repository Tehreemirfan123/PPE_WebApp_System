"""
Router: CRUD /workers/   (admin-only)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
import shutil, os

from backend.database import get_db
from backend import schemas, crud, models
from backend.auth import require_admin
from backend.config import settings

router = APIRouter(prefix="/workers", tags=["Workers"])


@router.get("/", response_model=List[schemas.WorkerOut])
def list_workers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    return crud.get_workers(db, skip=skip, limit=limit)


@router.get("/{employee_id}", response_model=schemas.WorkerOut)
def get_worker(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    worker = crud.get_worker_by_employee_id(db, employee_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker


@router.post("/", response_model=schemas.WorkerOut, status_code=status.HTTP_201_CREATED)
def create_worker(
    worker: schemas.WorkerCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if crud.get_worker_by_employee_id(db, worker.employee_id):
        raise HTTPException(status_code=400, detail="Employee ID already exists")
    return crud.create_worker(db, worker)


@router.post("/{employee_id}/upload-face", response_model=schemas.WorkerOut)
def upload_face_photo(
    employee_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """Upload a face photo for a worker. ML pipeline will later generate the embedding."""
    worker = crud.get_worker_by_employee_id(db, employee_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    faces_dir = os.path.join(settings.saved_violations_dir, "..", "worker_faces")
    os.makedirs(faces_dir, exist_ok=True)
    file_path = os.path.join(faces_dir, f"worker_{employee_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    updates = schemas.WorkerUpdate(face_image_path=file_path)
    return crud.update_worker(db, employee_id, updates)


@router.put("/{employee_id}", response_model=schemas.WorkerOut)
def update_worker(
    employee_id: str,
    updates: schemas.WorkerUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    worker = crud.update_worker(db, employee_id, updates)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_worker(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if not crud.delete_worker(db, employee_id):
        raise HTTPException(status_code=404, detail="Worker not found")
