from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.schemas import OverviewOut
from services.api.services.overview import get_overview

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("", response_model=OverviewOut)
def overview(db: Session = Depends(get_db)) -> OverviewOut:
    return get_overview(db)
