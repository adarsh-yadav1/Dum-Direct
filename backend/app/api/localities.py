"""Area search for the delivery picker. Public; the list is a fixed set of named places (assumption A3)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Locality

router = APIRouter(tags=["localities"])


class LocalityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    city: str
    latitude: float
    longitude: float


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/localities", response_model=list[LocalityOut])
def search_localities(
    q: Annotated[str, Query(max_length=60)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
) -> list[Locality]:
    """Areas whose name contains the text, case-insensitively. Names that start with it come first."""
    term = q.strip()
    query = select(Locality).limit(limit)
    if term:
        starts = Locality.name.ilike(f"{_escape_like(term)}%", escape="\\")
        query = query.where(Locality.name.ilike(f"%{_escape_like(term)}%", escape="\\")).order_by(
            case((starts, 0), else_=1), Locality.city, Locality.name
        )
    else:
        query = query.order_by(Locality.city, Locality.name)
    return list(db.scalars(query))
