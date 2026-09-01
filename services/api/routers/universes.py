from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from services.api.db import get_db
from services.api.models import Universe, UniverseKind
from services.api.schemas import (
    UniverseCreate,
    UniverseMemberCreate,
    UniverseMemberOut,
    UniverseMemberUpdate,
    UniverseOut,
    UniversePage,
    UniverseUpdate,
)
from services.api.services import universes as universe_service

router = APIRouter(prefix="/universes", tags=["universes"])


def _to_out(universe: Universe, *, include_members: bool = True) -> UniverseOut:
    members = [
        UniverseMemberOut.model_validate(row)
        for row in sorted(universe.members, key=lambda m: (m.symbol, m.effective_from))
    ]
    return UniverseOut(
        id=universe.id,
        name=universe.name,
        description=universe.description,
        kind=universe.kind.value if isinstance(universe.kind, UniverseKind) else str(universe.kind),
        created_at=universe.created_at,
        updated_at=universe.updated_at,
        member_count=len(universe.members),
        members=members if include_members else [],
    )


@router.get("", response_model=UniversePage)
def list_universes(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> UniversePage:
    rows, total = universe_service.list_universes(db, limit=limit, offset=offset)
    return UniversePage(
        items=[_to_out(row, include_members=False) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=UniverseOut, status_code=status.HTTP_201_CREATED)
def create_universe(payload: UniverseCreate, db: Session = Depends(get_db)) -> UniverseOut:
    universe = universe_service.create_universe(
        db, payload.name, payload.description, payload.members
    )
    return _to_out(universe)


@router.get("/{universe_id}", response_model=UniverseOut)
def get_universe(universe_id: UUID, db: Session = Depends(get_db)) -> UniverseOut:
    return _to_out(universe_service.get_universe(db, universe_id))


@router.patch("/{universe_id}", response_model=UniverseOut)
def update_universe(
    universe_id: UUID, payload: UniverseUpdate, db: Session = Depends(get_db)
) -> UniverseOut:
    return _to_out(
        universe_service.update_universe(
            db, universe_id, name=payload.name, description=payload.description
        )
    )


@router.delete("/{universe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_universe(universe_id: UUID, db: Session = Depends(get_db)) -> Response:
    universe_service.delete_universe(db, universe_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{universe_id}/members",
    response_model=UniverseMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    universe_id: UUID, payload: UniverseMemberCreate, db: Session = Depends(get_db)
) -> UniverseMemberOut:
    return UniverseMemberOut.model_validate(universe_service.add_member(db, universe_id, payload))


@router.patch("/{universe_id}/members/{member_id}", response_model=UniverseMemberOut)
def update_member(
    universe_id: UUID,
    member_id: UUID,
    payload: UniverseMemberUpdate,
    db: Session = Depends(get_db),
) -> UniverseMemberOut:
    to_provided = "effective_to" in payload.model_fields_set
    row = universe_service.update_member(
        db,
        universe_id,
        member_id,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        infer=payload.infer_effective_to_from_data,
        to_provided=to_provided,
    )
    return UniverseMemberOut.model_validate(row)


@router.delete("/{universe_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(universe_id: UUID, member_id: UUID, db: Session = Depends(get_db)) -> Response:
    universe_service.delete_member(db, universe_id, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{universe_id}/constituents")
def preview_constituents(
    universe_id: UUID,
    as_of: date | None = None,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict:
    universe = universe_service.get_universe(db, universe_id)
    return universe_service.preview_constituents(universe, as_of=as_of, start=start, end=end)
