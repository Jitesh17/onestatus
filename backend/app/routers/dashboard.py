"""Dashboard endpoint (week 5): fixed manager KPIs aggregated from the capture data.

Read-only. All computation lives in crud.dashboard_metrics; the route just serves it.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=schemas.DashboardOut)
def get_dashboard(db: Session = Depends(get_db)):
    return crud.dashboard_metrics(db)
