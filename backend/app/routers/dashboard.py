"""Dashboard endpoints.

Week 5: GET /dashboard — fixed manager KPIs aggregated from the capture data (read-only).
Week 6: POST /dashboard/configure — interpret a natural-language command into a view-config
and return the filtered dashboard; POST /dashboard/apply — apply an explicit/saved config.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..view_interpreter import interpret_view, ExtractorError

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=schemas.DashboardOut)
def get_dashboard(db: Session = Depends(get_db)):
    return crud.dashboard_metrics(db)


@router.post("/configure", response_model=schemas.ConfiguredDashboard)
def configure_dashboard(data: schemas.ConfigureRequest, db: Session = Depends(get_db)):
    world = crud.build_world(db)
    try:
        config = interpret_view(data.request, world, model=data.model)
    except ExtractorError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    dashboard = crud.dashboard_metrics(db, config)
    return {"config": config, "dashboard": dashboard}


@router.post("/apply", response_model=schemas.ConfiguredDashboard)
def apply_view(data: schemas.ApplyRequest, db: Session = Depends(get_db)):
    config = data.config.model_dump()
    dashboard = crud.dashboard_metrics(db, config)
    return {"config": config, "dashboard": dashboard}
