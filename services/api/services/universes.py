from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from quant.data.ingest_spy import load_symbol_parquet
from quant.data.symbols import list_market_symbols, normalize_symbols
from quant.data.universe import (
    Membership,
    constituents_as_of,
    constituents_overlapping,
    infer_effective_to_from_bars,
    inferred_delistings,
    memberships_overlapping,
    validate_memberships,
)
from quant.data.universe_rules import evaluate_universe, parse_rules
from services.api.models import Universe, UniverseKind, UniverseMember
from services.api.schemas import UniverseMemberCreate
from services.api.settings import get_settings


def _memberships_of(universe: Universe) -> list[Membership]:
    return [
        Membership(
            symbol=row.symbol, effective_from=row.effective_from, effective_to=row.effective_to
        )
        for row in universe.members
    ]


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="同一标的在同一开始日已有成分区间",
        ) from exc


def list_universes(db: Session, *, limit: int = 50, offset: int = 0) -> tuple[list[Universe], int]:
    total = int(db.scalar(select(func.count()).select_from(Universe)) or 0)
    rows = list(
        db.scalars(
            select(Universe)
            .options(selectinload(Universe.members))
            .order_by(Universe.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return rows, total


def get_universe(db: Session, universe_id: UUID) -> Universe:
    universe = db.scalars(
        select(Universe).options(selectinload(Universe.members)).where(Universe.id == universe_id)
    ).first()
    if not universe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标的池不存在")
    return universe


def _to_member_row(
    universe_id: UUID, payload: UniverseMemberCreate, data_root: Path
) -> UniverseMember:
    try:
        symbol = normalize_symbols([payload.symbol])[0]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    effective_to = payload.effective_to
    if payload.infer_effective_to_from_data and payload.effective_to is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能同时指定 effective_to 和从数据推断退市日",
        )
    if payload.infer_effective_to_from_data:
        try:
            frame = load_symbol_parquet(data_root, symbol)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"没有 {symbol} 行情，无法从数据推断 effective_to。请先摄取该标的。",
            ) from exc
        last = frame["timestamp"].max()
        last_day = last.date() if hasattr(last, "date") else date.fromisoformat(str(last)[:10])
        effective_to = infer_effective_to_from_bars(last_day)
    return UniverseMember(
        universe_id=universe_id,
        symbol=symbol,
        effective_from=payload.effective_from,
        effective_to=effective_to,
    )


def create_universe(
    db: Session,
    name: str,
    description: str | None,
    members: list[UniverseMemberCreate],
    *,
    kind: str = "STATIC",
    rules: dict | None = None,
) -> Universe:
    existing = db.scalars(select(Universe).where(Universe.name == name.strip())).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有同名标的池")
    try:
        universe_kind = UniverseKind(kind.strip().upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="kind 只能是 STATIC 或 RULE",
        ) from exc
    parsed_rules = None
    if universe_kind is UniverseKind.RULE:
        if members:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RULE 标的池的成分由规则生成，不能手工写入 members",
            )
        try:
            parsed_rules = parse_rules(rules).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    elif rules is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="STATIC 标的池不能带 rules",
        )
    universe = Universe(
        name=name.strip(),
        description=description,
        kind=universe_kind,
        rules=parsed_rules,
    )
    db.add(universe)
    db.flush()
    data_root = Path(get_settings().data_root)
    rows = [_to_member_row(universe.id, item, data_root) for item in members]
    try:
        validate_memberships(
            [
                Membership(
                    symbol=r.symbol, effective_from=r.effective_from, effective_to=r.effective_to
                )
                for r in rows
            ]
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.add_all(rows)
    _commit_or_conflict(db)
    if universe_kind is UniverseKind.RULE:
        return rebuild_rule_universe(db, universe.id)
    return get_universe(db, universe.id)


def update_universe(
    db: Session,
    universe_id: UUID,
    *,
    name: str | None,
    description: str | None,
    rules: dict | None = None,
) -> Universe:
    universe = get_universe(db, universe_id)
    if name is not None:
        clash = db.scalars(
            select(Universe).where(Universe.name == name.strip(), Universe.id != universe_id)
        ).first()
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有同名标的池")
        universe.name = name.strip()
    if description is not None:
        universe.description = description
    if rules is not None:
        if universe.kind != UniverseKind.RULE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只有 RULE 标的池能改 rules",
            )
        try:
            universe.rules = parse_rules(rules).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return get_universe(db, universe_id)


def delete_universe(db: Session, universe_id: UUID) -> None:
    universe = get_universe(db, universe_id)
    db.delete(universe)
    db.commit()


def add_member(db: Session, universe_id: UUID, payload: UniverseMemberCreate) -> UniverseMember:
    universe = get_universe(db, universe_id)
    if universe.kind == UniverseKind.RULE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RULE 标的池请用「按规则重建」，不能手工改成分",
        )
    data_root = Path(get_settings().data_root)
    row = _to_member_row(universe.id, payload, data_root)
    proposed = _memberships_of(universe) + [
        Membership(
            symbol=row.symbol, effective_from=row.effective_from, effective_to=row.effective_to
        )
    ]
    try:
        validate_memberships(proposed)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.add(row)
    _commit_or_conflict(db)
    db.refresh(row)
    return row


def update_member(
    db: Session,
    universe_id: UUID,
    member_id: UUID,
    *,
    effective_from: date | None,
    effective_to: date | None,
    infer: bool,
    to_provided: bool,
) -> UniverseMember:
    universe = get_universe(db, universe_id)
    row = db.get(UniverseMember, member_id)
    if row is None or row.universe_id != universe.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成分不存在")
    if universe.kind == UniverseKind.RULE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RULE 标的池请用「按规则重建」，不能手工改成分",
        )
    if infer and to_provided:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能同时指定 effective_to 和从数据推断退市日",
        )
    if effective_from is not None:
        row.effective_from = effective_from
    if infer:
        data_root = Path(get_settings().data_root)
        try:
            frame = load_symbol_parquet(data_root, row.symbol)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"没有 {row.symbol} 行情，无法从数据推断 effective_to。",
            ) from exc
        last = frame["timestamp"].max()
        last_day = last.date() if hasattr(last, "date") else date.fromisoformat(str(last)[:10])
        row.effective_to = infer_effective_to_from_bars(last_day)
    elif to_provided:
        row.effective_to = effective_to
    proposed = [
        Membership(
            symbol=item.symbol, effective_from=item.effective_from, effective_to=item.effective_to
        )
        for item in universe.members
    ]
    try:
        validate_memberships(proposed)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _commit_or_conflict(db)
    db.refresh(row)
    return row


def delete_member(db: Session, universe_id: UUID, member_id: UUID) -> None:
    universe = get_universe(db, universe_id)
    if universe.kind == UniverseKind.RULE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RULE 标的池请用「按规则重建」，不能手工改成分",
        )
    row = db.get(UniverseMember, member_id)
    if row is None or row.universe_id != universe.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成分不存在")
    db.delete(row)
    db.commit()


def resolve_for_range(universe: Universe, start: date, end: date) -> list[Membership]:
    try:
        members = _memberships_of(universe)
        validate_memberships(members)
        return memberships_overlapping(members, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def preview_constituents(
    universe: Universe, *, as_of: date | None, start: date | None, end: date | None
) -> dict:
    members = _memberships_of(universe)
    if as_of is not None:
        return {"as_of": as_of.isoformat(), "symbols": constituents_as_of(members, as_of)}
    if start is not None and end is not None:
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "symbols": constituents_overlapping(members, start, end),
            "memberships": [m.to_dict() for m in memberships_overlapping(members, start, end)],
        }
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="需要 as_of，或同时提供 start 与 end",
    )


def _last_bar_date(frame) -> date:
    last = frame["timestamp"].max()
    if hasattr(last, "date"):
        return last.date()
    return date.fromisoformat(str(last)[:10])


def apply_inferred_delistings(db: Session, delistings: list[dict[str, str]]) -> dict:
    """Close open-ended memberships from stale last bars.

    Never overwrite an existing effective_to. Never invent a live listing.
    """
    applied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    by_symbol: dict[str, date] = {}
    for row in delistings:
        symbol = str(row["symbol"]).upper()
        by_symbol[symbol] = date.fromisoformat(str(row["effective_to"])[:10])
    if not by_symbol:
        return {"applied": applied, "skipped": skipped, "errors": errors}

    members = list(
        db.scalars(select(UniverseMember).where(UniverseMember.symbol.in_(list(by_symbol)))).all()
    )
    for member in members:
        inferred = by_symbol[member.symbol]
        if member.effective_to is not None:
            skipped.append(
                {
                    "universe_id": str(member.universe_id),
                    "symbol": member.symbol,
                    "effective_to": member.effective_to.isoformat(),
                    "reason": "existing_effective_to_preserved",
                }
            )
            if member.effective_to != inferred:
                errors.append(
                    {
                        "universe_id": str(member.universe_id),
                        "symbol": member.symbol,
                        "message": (
                            f"已有 effective_to {member.effective_to} 与本次推断 "
                            f"{inferred} 不一致，拒绝覆盖"
                        ),
                    }
                )
            continue
        if inferred < member.effective_from:
            errors.append(
                {
                    "universe_id": str(member.universe_id),
                    "symbol": member.symbol,
                    "message": (
                        f"推断退出日 {inferred} 早于进入日 {member.effective_from}，拒绝改写"
                    ),
                }
            )
            continue
        member.effective_to = inferred
        applied.append(
            {
                "universe_id": str(member.universe_id),
                "symbol": member.symbol,
                "effective_to": inferred.isoformat(),
            }
        )
    return {"applied": applied, "skipped": skipped, "errors": errors}


def sync_delistings_from_data(db: Session, *, as_of: date | None = None) -> dict:
    """Infer delist dates from current parquets for every open-ended member."""
    data_root = Path(get_settings().data_root)
    open_members = list(
        db.scalars(select(UniverseMember).where(UniverseMember.effective_to.is_(None))).all()
    )
    last_bars: dict[str, date] = {}
    missing: list[dict[str, str]] = []
    seen: set[str] = set()
    for member in open_members:
        if member.symbol in seen:
            continue
        seen.add(member.symbol)
        try:
            frame = load_symbol_parquet(data_root, member.symbol)
        except FileNotFoundError:
            missing.append(
                {
                    "universe_id": str(member.universe_id),
                    "symbol": member.symbol,
                    "message": f"没有 {member.symbol} 行情，无法推断 effective_to",
                }
            )
            continue
        last_bars[member.symbol] = _last_bar_date(frame)
    delistings = inferred_delistings(last_bars, as_of=as_of)
    result = apply_inferred_delistings(db, delistings)
    result["errors"] = list(result["errors"]) + missing
    result["inferred"] = delistings
    db.commit()
    return result


def rebuild_rule_universe(db: Session, universe_id: UUID) -> Universe:
    universe = get_universe(db, universe_id)
    if universe.kind != UniverseKind.RULE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有 RULE 标的池能按规则重建",
        )
    try:
        rules = parse_rules(universe.rules)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    data_root = Path(get_settings().data_root)
    symbols = list_market_symbols(data_root)
    if not symbols:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="还没有行情快照，无法按流动性规则生成成分。请先拉取标的。",
        )
    frames = {symbol: load_symbol_parquet(data_root, symbol) for symbol in symbols}
    try:
        derived = evaluate_universe(frames, rules)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    for row in list(universe.members):
        db.delete(row)
    db.flush()
    db.add_all(
        [
            UniverseMember(
                universe_id=universe.id,
                symbol=member.symbol,
                effective_from=member.effective_from,
                effective_to=member.effective_to,
            )
            for member in derived
        ]
    )
    db.commit()
    return get_universe(db, universe.id)
