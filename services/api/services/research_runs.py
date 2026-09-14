"""P4.3 bounded research runs: steps are persisted, idempotent and checkpointed;
budgets stop new work instead of silently overspending.

The runner is deterministic and local — no model call is required to advance a
step. Each step carries an idempotency key ``{run_id}:{index}`` and replays its
stored output if it is executed twice. The checkpoint records the next index and
the collected outputs, so a restart continues where it stopped.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.models import (
    ResearchRun,
    ResearchRunStatus,
    ResearchStep,
    ResearchStepStatus,
    Strategy,
)

STEP_KINDS = ("draft_rules", "compile", "review", "backtest", "summarize")
DEFAULT_BUDGET = {"max_steps": 5, "max_lean_runs": 1, "max_minutes": 30}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_run(db: Session, run_id: UUID) -> ResearchRun:
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究运行不存在")
    return run


def create_run(
    db: Session,
    *,
    goal: str,
    strategy_id: UUID | None = None,
    budget: dict[str, Any] | None = None,
) -> ResearchRun:
    if strategy_id is not None and db.get(Strategy, strategy_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="策略不存在")
    merged_budget = {**DEFAULT_BUDGET, **(budget or {})}
    run = ResearchRun(
        strategy_id=strategy_id,
        goal=goal or "",
        status=ResearchRunStatus.RUNNING,
        budget=merged_budget,
        spent={"steps": 0, "lean_runs": 0, "minutes": 0.0},
        checkpoint={"next_index": 0, "outputs": {}},
    )
    db.add(run)
    db.flush()
    for index, name in enumerate(("draft_rules", "compile", "review", "summarize")):
        db.add(
            ResearchStep(
                run_id=run.id,
                index=index,
                name=name,
                status=ResearchStepStatus.PENDING,
                idempotency_key=f"{run.id}:{index}",
                input={},
                output={},
            )
        )
    db.commit()
    db.refresh(run)
    return run


def _pending_step(db: Session, run: ResearchRun) -> ResearchStep | None:
    index = int((run.checkpoint or {}).get("next_index", 0))
    return db.scalars(
        select(ResearchStep)
        .where(ResearchStep.run_id == run.id, ResearchStep.index == index)
        .limit(1)
    ).first()


def _budget_allows(run: ResearchRun, *, lean_runs: int = 0, minutes: float = 0.0) -> bool:
    budget = run.budget or {}
    spent = run.spent or {}
    if int(spent.get("steps", 0)) + 1 > int(budget.get("max_steps", 0)):
        return False
    if int(spent.get("lean_runs", 0)) + lean_runs > int(budget.get("max_lean_runs", 0)):
        return False
    return float(spent.get("minutes", 0.0)) + minutes <= float(budget.get("max_minutes", 0))


def _execute_step(db: Session, run: ResearchRun, step: ResearchStep) -> dict[str, Any]:
    """Deterministic, local step execution. No network, no model."""
    outputs = dict((run.checkpoint or {}).get("outputs") or {})
    if step.name == "draft_rules":
        from services.agent.rules import draft_rules_from_intent

        draft = draft_rules_from_intent(run.goal)
        return {"draft": draft.to_dict(), "unsupported": draft.unsupported}
    if step.name == "compile":
        from services.agent.rules import RuleDraft, compile_trend_rules

        raw = (outputs.get("draft_rules") or {}).get("draft") or {}
        draft = RuleDraft(
            template=raw.get("template", "trend"),
            symbol=raw.get("symbol", "SPY"),
            lookback=raw.get("lookback"),
            position_pct=float(raw.get("position_pct", 100)),
            slippage_bps=float(raw.get("slippage_bps", 5)),
            hypothesis=raw.get("hypothesis", run.goal),
            unsupported=list(raw.get("unsupported") or []),
        )
        code, config = compile_trend_rules(draft)
        return {"code": code, "config": config}
    if step.name == "review":
        from services.agent.rule_review import review_rule_change

        compiled = outputs.get("compile") or {}
        report = review_rule_change(
            current_code="",
            proposed_code=str(compiled.get("code", "")),
            unsupported=list((outputs.get("draft_rules") or {}).get("unsupported") or []),
        )
        return report
    if step.name == "summarize":
        return {
            "citations": {
                "draft": bool(outputs.get("draft_rules")),
                "compiled_code_len": len(str((outputs.get("compile") or {}).get("code", ""))),
                "review_approvable": bool((outputs.get("review") or {}).get("approvable")),
            },
            "note": "本步骤只汇总已产出的本地产物；不会声称验证通过。",
        }
    raise ValueError(f"未知步骤 {step.name}")


def advance_run(db: Session, run_id: UUID) -> ResearchRun:
    """Execute the next pending step once (idempotent) and persist the checkpoint."""
    run = _get_run(db, run_id)
    if run.status in {ResearchRunStatus.COMPLETED, ResearchRunStatus.CANCELLED}:
        raise HTTPException(
            status_code=409, detail=f"运行已处于终态 {run.status.value}，不能继续。"
        )
    if run.status == ResearchRunStatus.PAUSED:
        raise HTTPException(status_code=409, detail="运行已暂停：请先恢复再继续。")

    step = _pending_step(db, run)
    if step is None:
        run.status = ResearchRunStatus.COMPLETED
        db.commit()
        db.refresh(run)
        return run

    # 幂等：重复推进同一步骤直接回放已存输出，不重复副作用。
    if step.status == ResearchStepStatus.COMPLETED:
        checkpoint = dict(run.checkpoint or {})
        checkpoint["next_index"] = int(checkpoint.get("next_index", 0)) + 1
        run.checkpoint = checkpoint
        db.commit()
        db.refresh(run)
        return run

    if not _budget_allows(run, lean_runs=1 if step.name == "backtest" else 0):
        run.status = ResearchRunStatus.PAUSED
        run.error = "预算已用尽：该步骤未执行。提高预算后恢复运行。"
        db.commit()
        db.refresh(run)
        return run

    step.status = ResearchStepStatus.RUNNING
    db.commit()
    try:
        output = _execute_step(db, run, step)
        step.output = output
        step.status = ResearchStepStatus.COMPLETED
        step.finished_at = _now()
        spent = dict(run.spent or {})
        spent["steps"] = int(spent.get("steps", 0)) + 1
        run.spent = spent
        checkpoint = dict(run.checkpoint or {})
        outputs = dict(checkpoint.get("outputs") or {})
        outputs[step.name] = output
        checkpoint["outputs"] = outputs
        checkpoint["next_index"] = int(checkpoint.get("next_index", 0)) + 1
        run.checkpoint = checkpoint
        if _pending_step(db, run) is None:
            run.status = ResearchRunStatus.COMPLETED
        db.commit()
    except Exception as exc:  # noqa: BLE001 - 记录失败并停在可恢复点
        step.status = ResearchStepStatus.FAILED
        step.output = {"error": str(exc)}
        step.finished_at = _now()
        run.status = ResearchRunStatus.FAILED
        run.error = str(exc)
        db.commit()
    db.refresh(run)
    return run


def pause_run(db: Session, run_id: UUID) -> ResearchRun:
    run = _get_run(db, run_id)
    if run.status == ResearchRunStatus.RUNNING:
        run.status = ResearchRunStatus.PAUSED
        db.commit()
        db.refresh(run)
    return run


def resume_run(db: Session, run_id: UUID) -> ResearchRun:
    run = _get_run(db, run_id)
    if run.status == ResearchRunStatus.PAUSED:
        run.status = ResearchRunStatus.RUNNING
        run.error = None
        db.commit()
        db.refresh(run)
    return run


def cancel_run(db: Session, run_id: UUID) -> ResearchRun:
    run = _get_run(db, run_id)
    if run.status not in {ResearchRunStatus.COMPLETED, ResearchRunStatus.CANCELLED}:
        run.status = ResearchRunStatus.CANCELLED
        db.commit()
        db.refresh(run)
    return run


def run_state(db: Session, run_id: UUID) -> dict[str, Any]:
    run = _get_run(db, run_id)
    steps = list(
        db.scalars(
            select(ResearchStep)
            .where(ResearchStep.run_id == run.id)
            .order_by(ResearchStep.index.asc())
        ).all()
    )
    return {
        "id": str(run.id),
        "strategy_id": str(run.strategy_id) if run.strategy_id else None,
        "goal": run.goal,
        "status": run.status.value,
        "budget": run.budget,
        "spent": run.spent,
        "checkpoint": run.checkpoint,
        "error": run.error,
        "steps": [
            {
                "index": step.index,
                "name": step.name,
                "status": step.status.value,
                "idempotency_key": step.idempotency_key,
                "output": step.output,
            }
            for step in steps
        ],
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }
