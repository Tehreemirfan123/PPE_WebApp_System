"""
Router: CRUD /sites/
Default sites are protected from update/delete.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import schemas, crud, models
from backend.auth import require_admin, get_current_user

router = APIRouter(prefix="/sites", tags=["Sites"])


@router.get("/", response_model=List[schemas.SiteOut])
def list_sites(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_sites(db, skip=skip, limit=limit)


@router.get("/{site_name}", response_model=schemas.SiteOut)
def get_site(
    site_name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    site = crud.get_site_by_name(db, site_name)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.post("/", response_model=schemas.SiteOut, status_code=status.HTTP_201_CREATED)
def create_site(
    site: schemas.SiteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    return crud.create_site(db, site)


@router.put("/{site_name}", response_model=schemas.SiteOut)
def update_site(
    site_name: str,
    updates: schemas.SiteUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    site = crud.get_site_by_name(db, site_name)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    if site.is_default:
        raise HTTPException(status_code=403, detail="Default sites cannot be modified")
    updated = crud.update_site(db, site_name, updates)
    return updated


@router.delete("/{site_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_site(
    site_name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    site = crud.get_site_by_name(db, site_name)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    if site.is_default:
        raise HTTPException(status_code=403, detail="Default sites cannot be deleted")
    crud.delete_site(db, site_name)
