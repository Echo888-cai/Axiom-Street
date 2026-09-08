"""P5-4 guided Copilot chat contract and execution tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from services.agent.copilot.insights import list_chat_messages
from services.api.db import Base
from services.api.models import CopilotChatMessage, CopilotChatStatus, Strategy
from services.api.schemas import CopilotChatIn


def test_chat_input_rejects_blank_and_overlong_messages() -> None:
    with pytest.raises(ValidationError):
        CopilotChatIn(resource="strategy", id=uuid4(), message="   ")
    with pytest.raises(ValidationError):
        CopilotChatIn(resource="strategy", id=uuid4(), message="x" * 1201)


def test_chat_input_strips_surrounding_whitespace() -> None:
    payload = CopilotChatIn(resource="backtest", id=uuid4(), message="  是否该停？  ")
    assert payload.message == "是否该停？"


def test_chat_ledger_has_auditable_status_and_payload() -> None:
    strategy_id = uuid4()
    row = CopilotChatMessage(
        strategy_id=strategy_id,
        resource="strategy",
        resource_id=strategy_id,
        user_message="下一步验证什么？",
        status=CopilotChatStatus.QUEUED,
    )
    assert row.status is CopilotChatStatus.QUEUED
    assert row.strategy_id == strategy_id
    assert row.user_message == "下一步验证什么？"
    assert {status.value for status in CopilotChatStatus} == {"QUEUED", "DONE", "FAILED"}


def test_list_chat_messages_returns_newest_first() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    strategy_id = uuid4()
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(Strategy(id=strategy_id, name="Chat strategy", benchmark="SPY"))
        db.add_all(
            [
                CopilotChatMessage(
                    strategy_id=strategy_id,
                    resource="strategy",
                    resource_id=strategy_id,
                    user_message="旧问题",
                    assistant_message="旧回答",
                    status=CopilotChatStatus.DONE,
                    created_at=now - timedelta(minutes=1),
                ),
                CopilotChatMessage(
                    strategy_id=strategy_id,
                    resource="strategy",
                    resource_id=strategy_id,
                    user_message="新问题",
                    assistant_message="新回答",
                    status=CopilotChatStatus.DONE,
                    created_at=now,
                ),
            ]
        )
        db.commit()

        rows = list_chat_messages(db, strategy_id)

    assert [row["user_message"] for row in rows] == ["新问题", "旧问题"]
