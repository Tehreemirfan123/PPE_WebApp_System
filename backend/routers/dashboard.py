"""
Router: GET /dashboard/stats/
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import schemas, crud, models
from backend.auth import require_officer_or_admin

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats/", response_model=schemas.DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_officer_or_admin),
):
    return crud.get_dashboard_stats(db)
