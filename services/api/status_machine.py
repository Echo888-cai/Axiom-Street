from __future__ import annotations

from fastapi import HTTPException, status

from services.api.models import StrategyStatus

# Client PATCH may only archive, rename-adjacent draft resets, or stay put.
# VALIDATED / PAPER / APPROVED / LIVE / PAUSED are system-owned (belief 2).
_CLIENT_ALLOWED: dict[StrategyStatus, set[StrategyStatus]] = {
    StrategyStatus.DRAFT: {StrategyStatus.DRAFT, StrategyStatus.ARCHIVED},
    StrategyStatus.BACKTESTED: {
        StrategyStatus.DRAFT,
        StrategyStatus.BACKTESTED,
        StrategyStatus.ARCHIVED,
    },
    StrategyStatus.ARCHIVED: {StrategyStatus.ARCHIVED, StrategyStatus.DRAFT},
    StrategyStatus.VALIDATED: {StrategyStatus.VALIDATED, StrategyStatus.ARCHIVED},
    StrategyStatus.PAPER: {StrategyStatus.PAPER, StrategyStatus.ARCHIVED},
    StrategyStatus.APPROVED: {StrategyStatus.APPROVED, StrategyStatus.ARCHIVED},
    StrategyStatus.LIVE: {StrategyStatus.LIVE, StrategyStatus.PAUSED, StrategyStatus.ARCHIVED},
    StrategyStatus.PAUSED: {StrategyStatus.PAUSED, StrategyStatus.ARCHIVED},
}

_SYSTEM_OWNED = {
    StrategyStatus.VALIDATED,
    StrategyStatus.PAPER,
    StrategyStatus.APPROVED,
    StrategyStatus.LIVE,
    StrategyStatus.PAUSED,
}


def assert_client_status_transition(current: StrategyStatus, target: StrategyStatus) -> None:
    if target == current:
        return
    if target in _SYSTEM_OWNED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "status_transition_forbidden",
                "message": "VALIDATED 及以上状态只能由系统流程设置，不能由客户端直接写入。",
                "current": current.value,
                "requested": target.value,
            },
        )
    allowed = _CLIENT_ALLOWED.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "status_transition_forbidden",
                "message": f"不允许从 {current.value} 转换到 {target.value}",
                "current": current.value,
                "requested": target.value,
            },
        )
