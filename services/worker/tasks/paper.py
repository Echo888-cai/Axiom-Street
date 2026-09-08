"""Risk-gated paper execution worker (E6-1).

The task is the only side-effecting paper execution entry point. It reads the
latest strategy risk configuration, applies the pure execution domain rules,
and commits order/fill/account/position/reconciliation state together.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from quant.execution.paper import (
    FillRecord,
    PaperOrderCommand,
    PositionState,
    rebuild_positions,
    risk_target,
)
from quant.risk.limits import parse_risk_limits
from services.api.models import (
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PaperPosition,
    PaperReconciliation,
    PaperReconciliationStatus,
    Strategy,
    StrategyStatus,
    StrategyVersion,
)
from services.worker import tasks as _tasks
from services.worker.celery_app import celery_app

DEFAULT_PAPER_CAPITAL = 100_000.0
_EPS = 1e-9
_PAPER_STATUSES = {StrategyStatus.VALIDATED, StrategyStatus.PAPER, StrategyStatus.APPROVED}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _position_state(row: PaperPosition | None, price: float) -> PositionState:
    if row is None:
        return PositionState(0.0, 0.0, 0.0, price)
    return PositionState(row.quantity, row.average_price, row.realized_pnl, price)


def _account(db, strategy_id: UUID) -> PaperAccount:
    account = db.scalar(select(PaperAccount).where(PaperAccount.strategy_id == strategy_id))
    if account is None:
        account = PaperAccount(
            strategy_id=strategy_id,
            initial_capital=DEFAULT_PAPER_CAPITAL,
            cash=DEFAULT_PAPER_CAPITAL,
        )
        db.add(account)
        db.flush()
    return account


def _exposure(
    db, strategy_id: UUID, account: PaperAccount, symbol: str, price: float
) -> tuple[float, float, float]:
    rows = list(
        db.scalars(select(PaperPosition).where(PaperPosition.strategy_id == strategy_id)).all()
    )
    equity = account.cash + sum(
        row.quantity * (price if row.symbol == symbol else row.mark_price) for row in rows
    )
    if equity <= 0:
        raise ValueError("paper account equity must remain positive")
    gross = sum(
        abs(row.quantity * (price if row.symbol == symbol else row.mark_price) / equity)
        for row in rows
    )
    net = sum(
        row.quantity * (price if row.symbol == symbol else row.mark_price) / equity for row in rows
    )
    return equity, gross, net


def _fill_records(db, strategy_id: UUID) -> list[FillRecord]:
    rows = db.scalars(
        select(PaperFill).where(PaperFill.strategy_id == strategy_id).order_by(PaperFill.created_at)
    ).all()
    return [FillRecord(row.symbol, row.side.value, row.quantity, row.price) for row in rows]


def _write_reconciliation(db, strategy_id: UUID) -> PaperReconciliation:
    expected = rebuild_positions(_fill_records(db, strategy_id))
    actual_rows = list(
        db.scalars(select(PaperPosition).where(PaperPosition.strategy_id == strategy_id)).all()
    )
    expected_json = {
        symbol: {
            "quantity": position.quantity,
            "average_price": position.average_price,
            "realized_pnl": position.realized_pnl,
            "mark_price": position.mark_price,
        }
        for symbol, position in expected.items()
    }
    actual_json = {
        row.symbol: {
            "quantity": row.quantity,
            "average_price": row.average_price,
            "realized_pnl": row.realized_pnl,
            "mark_price": row.mark_price,
        }
        for row in actual_rows
    }
    differences: dict[str, Any] = {}
    for symbol in sorted(set(expected_json) | set(actual_json)):
        if expected_json.get(symbol) != actual_json.get(symbol):
            differences[symbol] = {
                "expected": expected_json.get(symbol),
                "actual": actual_json.get(symbol),
            }
    reconciliation = PaperReconciliation(
        strategy_id=strategy_id,
        status=(
            PaperReconciliationStatus.MATCHED
            if not differences
            else PaperReconciliationStatus.DRIFT
        ),
        expected_positions=expected_json,
        actual_positions=actual_json,
        differences=differences,
    )
    db.add(reconciliation)
    return reconciliation


def _update_position(db, strategy_id: UUID, command: PaperOrderCommand, quantity: float) -> None:
    row = db.scalar(
        select(PaperPosition).where(
            PaperPosition.strategy_id == strategy_id, PaperPosition.symbol == command.symbol
        )
    )
    current = _position_state(row, command.simulation_price)
    if command.side == "BUY":
        total = current.quantity + quantity
        current.average_price = (
            current.quantity * current.average_price + quantity * command.simulation_price
        ) / total
        current.quantity = total
    else:
        if quantity > current.quantity + _EPS:
            raise ValueError(
                f"cannot sell {quantity} {command.symbol}; only {current.quantity} held"
            )
        current.realized_pnl += (command.simulation_price - current.average_price) * quantity
        current.quantity -= quantity
        if abs(current.quantity) <= _EPS:
            current.quantity = 0.0
            current.average_price = 0.0
    current.mark_price = command.simulation_price
    if row is None:
        if current.quantity > _EPS:
            db.add(
                PaperPosition(
                    strategy_id=strategy_id,
                    symbol=command.symbol,
                    quantity=current.quantity,
                    average_price=current.average_price,
                    realized_pnl=current.realized_pnl,
                    mark_price=current.mark_price,
                )
            )
    elif current.quantity <= _EPS:
        db.delete(row)
    else:
        row.quantity = current.quantity
        row.average_price = current.average_price
        row.realized_pnl = current.realized_pnl
        row.mark_price = current.mark_price


def execute_paper_order(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute one paper order and return its auditable outcome."""
    try:
        strategy_id = UUID(str(payload["strategy_id"]))
        command = PaperOrderCommand(
            symbol=payload["symbol"],
            side=payload["side"],
            quantity=payload["quantity"],
            simulation_price=payload["simulation_price"],
            client_order_id=payload["client_order_id"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        return {"status": "failed", "error": str(exc)}

    with _tasks.SessionLocal() as db:
        existing = db.scalar(
            select(PaperOrder).where(
                PaperOrder.strategy_id == strategy_id,
                PaperOrder.client_order_id == command.client_order_id,
            )
        )
        if existing is not None:
            return {
                "status": "duplicate",
                "order_id": str(existing.id),
                "order_status": existing.status.value.lower(),
            }

        strategy = db.get(Strategy, strategy_id)
        if strategy is None:
            return {"status": "not_found", "detail": "策略不存在"}
        version = db.scalar(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == strategy_id)
            .order_by(StrategyVersion.version.desc())
        )
        order = PaperOrder(
            strategy_id=strategy_id,
            strategy_version_id=version.id if version else None,
            client_order_id=command.client_order_id,
            symbol=command.symbol,
            side=PaperOrderSide(command.side),
            requested_quantity=command.quantity,
            simulation_price=command.simulation_price,
            status=PaperOrderStatus.QUEUED,
        )
        db.add(order)
        db.flush()

        if strategy.status not in _PAPER_STATUSES:
            order.status = PaperOrderStatus.REJECTED
            order.error = "策略必须先通过验证才能进入纸面交易"
            order.finished_at = _now()
            db.commit()
            return {"status": "rejected", "order_id": str(order.id), "error": order.error}
        if version is None:
            order.status = PaperOrderStatus.FAILED
            order.error = "策略没有可执行版本"
            order.finished_at = _now()
            db.commit()
            return {"status": "failed", "order_id": str(order.id), "error": order.error}

        config = version.config if isinstance(version.config, dict) else {}
        try:
            limits = parse_risk_limits(config.get("risk_limits", {})).to_dict()
        except ValueError as exc:
            order.status = PaperOrderStatus.FAILED
            order.error = str(exc)
            order.finished_at = _now()
            db.commit()
            return {"status": "failed", "order_id": str(order.id), "error": str(exc)}

        try:
            account = _account(db, strategy_id)
            position_row = db.scalar(
                select(PaperPosition).where(
                    PaperPosition.strategy_id == strategy_id, PaperPosition.symbol == command.symbol
                )
            )
            position = _position_state(position_row, command.simulation_price)
            equity, gross, net = _exposure(
                db, strategy_id, account, command.symbol, command.simulation_price
            )
            decision = risk_target(
                symbol=command.symbol,
                side=command.side,
                quantity=command.quantity,
                simulation_price=command.simulation_price,
                account_equity=equity,
                position=position,
                gross_exposure=gross,
                net_exposure=net,
                orders_this_bar=0,
                risk_limits=limits,
            )
            if decision.allowed_quantity <= _EPS:
                raise ValueError(decision.reason or "risk gate rejected order")
        except ValueError as exc:
            order.status = PaperOrderStatus.REJECTED
            order.error = str(exc)
            order.risk_reason = str(exc)[:255]
            order.finished_at = _now()
            db.commit()
            return {
                "status": order.status.value.lower(),
                "order_id": str(order.id),
                "error": str(exc),
            }

        fill = PaperFill(
            order_id=order.id,
            strategy_id=strategy_id,
            symbol=command.symbol,
            side=PaperOrderSide(command.side),
            quantity=decision.allowed_quantity,
            price=command.simulation_price,
            fee=0.0,
        )
        db.add(fill)
        _update_position(db, strategy_id, command, decision.allowed_quantity)
        account.cash += (
            -decision.allowed_quantity * command.simulation_price
            if command.side == "BUY"
            else decision.allowed_quantity * command.simulation_price
        )
        order.status = PaperOrderStatus.FILLED
        order.filled_quantity = decision.allowed_quantity
        order.risk_reason = decision.reason
        order.risk_details = {
            "current_weight": decision.current_weight,
            "intended_weight": decision.intended_weight,
            "allowed_weight": decision.allowed_weight,
        }
        order.finished_at = _now()
        reconciliation = _write_reconciliation(db, strategy_id)
        db.commit()
        return {
            "status": "filled",
            "order_id": str(order.id),
            "filled_quantity": decision.allowed_quantity,
            "reconciliation": {"status": reconciliation.status.value},
        }


@celery_app.task(name="paper.execute_order")
def run_paper_order_task(payload: dict[str, Any]) -> dict[str, Any]:
    return execute_paper_order(payload)
