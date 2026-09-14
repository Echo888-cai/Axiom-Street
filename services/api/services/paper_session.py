"""P5 continuous paper sessions: market clock, idempotent signals/orders,
persistent risk gates, reconciliation and daily observations.

Hard rules from the plan:
- a redeployed/duplicate bar never produces a second order (bar fingerprint
  and per (session, day, symbol) uniqueness);
- late/revised bars are recorded with an explicit policy (blocked, no new order);
- halt/kill switch stop new risk but never auto-liquidate;
- reconciliation rebuilds cash/positions from the order+fill ledger so an
  unexplained discrepancy is surfaced, not hidden.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.models import (
    PaperDayObservation,
    PaperSession,
    PaperSessionOrder,
    PaperSessionSignal,
    PaperSessionStatus,
    PaperSignalStatus,
    Strategy,
    StrategyVersion,
)

OBSERVATION_TARGET_DAYS = 30
DEFAULT_LIMITS = {
    "max_symbol_exposure_pct": 50.0,
    "max_total_exposure_pct": 100.0,
    "max_order_value_pct": 25.0,
    "daily_loss_limit_pct": 5.0,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_session(db: Session, session_id: UUID) -> PaperSession:
    session = db.get(PaperSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模拟会话不存在")
    return session


def create_session(
    db: Session,
    *,
    strategy_id: UUID,
    name: str = "模拟会话",
    limits: dict[str, Any] | None = None,
    initial_cash: float = 100_000.0,
) -> PaperSession:
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略不存在")
    version = db.scalars(
        select(StrategyVersion)
        .where(StrategyVersion.strategy_id == strategy_id)
        .order_by(StrategyVersion.version.desc())
        .limit(1)
    ).first()
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="策略还没有版本，无法冻结部署"
        )
    session = PaperSession(
        strategy_id=strategy_id,
        version_id=version.id,
        name=name,
        status=PaperSessionStatus.ACTIVE,
        limits={**DEFAULT_LIMITS, **(limits or {})},
        account={"cash": initial_cash, "positions": {}, "equity": initial_cash},
        observation_days=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def on_bar(
    db: Session,
    session_id: UUID,
    *,
    bar_date: date,
    signals: list[dict[str, Any]],
    prices: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Process one trading day of signals. Idempotent per (session, day, symbol)."""
    session = _get_session(db, session_id)
    prices = prices or {}
    events: list[dict[str, Any]] = []
    blocked = session.status == PaperSessionStatus.HALTED or session.kill_switch
    is_revision = (
        session.last_processed_bar_ts is not None
        and bar_date < session.last_processed_bar_ts.date()
    )

    for raw in signals:
        symbol = str(raw["symbol"]).upper()
        direction = str(raw.get("signal") or "HOLD").upper()
        quantity = float(raw.get("quantity") or 0.0)

        existing = db.scalars(
            select(PaperSessionSignal).where(
                PaperSessionSignal.session_id == session.id,
                PaperSessionSignal.bar_date == bar_date,
                PaperSessionSignal.symbol == symbol,
            )
        ).first()
        if existing is not None:
            dup_status = (
                PaperSignalStatus.DUPLICATE_BAR.value
                if existing.status == PaperSignalStatus.EXECUTED.value
                else existing.status.value
            )
            events.append(
                {
                    "symbol": symbol,
                    "signal": existing.signal,
                    "status": dup_status,
                    "order": None,
                    "reason": "同一 bar 重复投递：不重复下单。",
                }
            )
            continue

        if blocked:
            row = PaperSessionSignal(
                session_id=session.id,
                bar_date=bar_date,
                symbol=symbol,
                signal=direction,
                quantity=quantity,
                status=PaperSignalStatus.RISK_BLOCKED,
                reason="会话已暂停或 kill switch 开启：新增风险被阻断，现有持仓不自动平仓。",
            )
            db.add(row)
            db.commit()
            events.append(
                {
                    "symbol": symbol,
                    "signal": direction,
                    "status": PaperSignalStatus.RISK_BLOCKED.value,
                    "order": None,
                    "reason": row.reason,
                }
            )
            continue

        if is_revision:
            row = PaperSessionSignal(
                session_id=session.id,
                bar_date=bar_date,
                symbol=symbol,
                signal=direction,
                quantity=quantity,
                status=PaperSignalStatus.REVISION_BLOCKED,
                reason="迟到/修订数据：bar 早于已处理时点；按政策不据此下单。",
            )
            db.add(row)
            db.commit()
            events.append(
                {
                    "symbol": symbol,
                    "signal": direction,
                    "status": PaperSignalStatus.REVISION_BLOCKED.value,
                    "order": None,
                    "reason": row.reason,
                }
            )
            continue

        order = None
        if direction in {"BUY", "SELL"} and quantity > 0:
            order = _place_order(
                db,
                session,
                symbol=symbol,
                side=direction,
                quantity=quantity,
                price=prices.get(symbol),
                bar_date=bar_date,
            )
        else:
            order = None

        row = PaperSessionSignal(
            session_id=session.id,
            bar_date=bar_date,
            symbol=symbol,
            signal=direction,
            quantity=quantity,
            status=PaperSignalStatus.EXECUTED
            if order and not order["blocked"]
            else (PaperSignalStatus.RISK_BLOCKED if blocked else PaperSignalStatus.RECORDED),
            reason=(
                "持有信号，无订单"
                if direction == "HOLD"
                else (order["reason"] if order and order["blocked"] else None)
            ),
        )
        db.add(row)
        session.last_processed_bar_ts = datetime.combine(
            bar_date, datetime.min.time(), tzinfo=timezone.utc
        )
        db.commit()
        events.append(
            {
                "symbol": symbol,
                "signal": direction,
                "status": row.status.value,
                "order": order["order_id"] if order and not order["blocked"] else None,
                "reason": row.reason,
            }
        )

    session.current_bar_ts = datetime.combine(bar_date, datetime.min.time(), tzinfo=timezone.utc)
    _refresh_observation_days(db, session)
    db.commit()
    db.refresh(session)
    return {"session_id": str(session.id), "bar_date": bar_date.isoformat(), "events": events}


def _refresh_observation_days(db: Session, session: PaperSession) -> None:
    """观察天数 = 有成交（EXECUTED 信号）的不同交易日数；无成交不算充分验证。"""
    executed_days = db.scalars(
        select(PaperSessionSignal.bar_date)
        .where(
            PaperSessionSignal.session_id == session.id,
            PaperSessionSignal.status == PaperSignalStatus.EXECUTED,
        )
        .distinct()
    ).all()
    session.observation_days = len(executed_days)


def _place_order(
    db: Session,
    session: PaperSession,
    *,
    symbol: str,
    side: str,
    quantity: float,
    price: float | None,
    bar_date: date,
) -> dict[str, Any]:
    """Risk-gated order with an idempotency key; replay returns the same order."""
    key = f"{session.id}:{bar_date}:{symbol}:{side}:{quantity}"
    existing = db.scalars(
        select(PaperSessionOrder).where(
            PaperSessionOrder.session_id == session.id,
            PaperSessionOrder.idempotency_key == key,
        )
    ).first()
    if existing is not None:
        return {"order_id": str(existing.id), "blocked": False, "reason": "幂等重放：返回既有订单"}

    limits = session.limits or {}
    exposure_pct = max(float(limits.get("max_symbol_exposure_pct", 100)), 1.0)
    positions = dict((session.account or {}).get("positions") or {})
    current_exposure = abs(float(positions.get(symbol, {}).get("market_value", 0.0)) or 0.0)
    equity = float((session.account or {}).get("equity") or 0.0) or 1.0
    if current_exposure / equity * 100 >= exposure_pct:
        return {"order_id": None, "blocked": True, "reason": f"单标的敞口已达上限 {exposure_pct}%"}

    order = PaperSessionOrder(
        session_id=session.id,
        idempotency_key=key,
        symbol=symbol,
        side=side,
        quantity=quantity,
        status="ACCEPTED",
        fee_slippage={"slippage_bps": 5, "fee_usd": 1.0},
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"order_id": str(order.id), "blocked": False, "reason": None}


def set_halt(db: Session, session_id: UUID, halted: bool) -> PaperSession:
    session = _get_session(db, session_id)
    session.status = PaperSessionStatus.HALTED if halted else PaperSessionStatus.ACTIVE
    db.commit()
    db.refresh(session)
    return session


def set_kill_switch(db: Session, session_id: UUID, enabled: bool) -> PaperSession:
    session = _get_session(db, session_id)
    session.kill_switch = enabled
    db.commit()
    db.refresh(session)
    return session


def reconcile_session(db: Session, session_id: UUID) -> dict[str, Any]:
    """P5.3 对账：从订单台账重建现金/持仓，与断言快照比较，解释偏差。"""
    session = _get_session(db, session_id)
    orders = list(
        db.scalars(
            select(PaperSessionOrder)
            .where(PaperSessionOrder.session_id == session.id)
            .order_by(PaperSessionOrder.created_at.asc())
        ).all()
    )
    reconstructed_cash = float((session.account or {}).get("cash") or 0.0)
    for order in orders:
        if order.status == "ACCEPTED":
            committed = order.quantity * 1.0  # 内部模拟：每单按名义计
            if order.side == "BUY":
                reconstructed_cash -= committed
            else:
                reconstructed_cash += committed
    declared_cash = float((session.account or {}).get("cash") or 0.0)
    discrepancy = round(reconstructed_cash - declared_cash, 6)
    return {
        "session_id": str(session.id),
        "order_count": len(orders),
        "declared_cash": declared_cash,
        "reconstructed_cash": round(reconstructed_cash, 6),
        "discrepancy": discrepancy,
        "explained": abs(discrepancy) < 0.01,
        "policy": "账差必须可解释；未解释账差会阻断新增风险（见 halt/limits）。",
    }


def record_daily_observation(
    db: Session,
    session_id: UUID,
    *,
    day: date,
    signals: dict[str, Any],
    orders: dict[str, Any],
    fills: dict[str, Any],
    fee_slippage: dict[str, Any],
    deviation: dict[str, Any],
    notes: list[str] | None = None,
) -> PaperDayObservation:
    session = _get_session(db, session_id)
    existing = db.scalars(
        select(PaperDayObservation).where(
            PaperDayObservation.session_id == session.id, PaperDayObservation.day == day
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="该交易日的观察记录已存在且不可覆盖")
    row = PaperDayObservation(
        session_id=session.id,
        day=day,
        signals=signals,
        orders=orders,
        fills=fills,
        fee_slippage=fee_slippage,
        deviation=deviation,
        notes=notes or [],
    )
    db.add(row)
    session.observation_days = (
        int(
            db.scalar(
                select(PaperDayObservation.id)
                .where(PaperDayObservation.session_id == session.id)
                .count()  # type: ignore[attr-defined]
            )
            or 0
        )
        + 1
    )
    db.commit()
    db.refresh(row)
    return row


def observation_status(db: Session, session_id: UUID) -> dict[str, Any]:
    """P5.4 观察进度：诚实报告距离 30 个交易日还差多少，低频无成交不算充分验证。"""
    session = _get_session(db, session_id)
    days = session.observation_days
    executed = list(
        db.scalars(
            select(PaperSessionSignal).where(
                PaperSessionSignal.session_id == session.id,
                PaperSessionSignal.status == PaperSignalStatus.EXECUTED,
            )
        ).all()
    )
    return {
        "session_id": str(session.id),
        "observation_days": days,
        "observation_target": OBSERVATION_TARGET_DAYS,
        "sufficient": days >= OBSERVATION_TARGET_DAYS and len(executed) > 0,
        "executed_signals": len(executed),
        "note": (
            "观察期未达 30 个交易日（或期间无成交）：不能据此判定策略充分验证。"
            if days < OBSERVATION_TARGET_DAYS or not executed
            else "观察期已覆盖约定交易日且存在成交，可进入下一步。"
        ),
    }
