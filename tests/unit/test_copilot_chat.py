"""P5-4 guided Copilot chat contract and execution tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.agent.copilot.insights import list_chat_messages
from services.agent.copilot.providers import CopilotProviderError
from services.api import db as db_module
from services.api.db import Base
from services.api.models import CopilotChatMessage, CopilotChatStatus, Strategy
from services.api.schemas import CopilotChatIn
from services.api.settings import get_settings
from services.worker.tasks.copilot import execute_chat


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


def _seed_strategy(db) -> Strategy:
    strategy = Strategy(id=uuid4(), name="Chat strategy", status="BACKTESTED", benchmark="SPY")
    db.add(strategy)
    db.commit()
    return strategy


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(db_module, "SessionLocal", SessionLocal)
    monkeypatch.setattr("services.worker.tasks.SessionLocal", SessionLocal)
    return SessionLocal


def _chat_rows(SessionLocal) -> list[CopilotChatMessage]:
    with SessionLocal() as db:
        return list(db.execute(select(CopilotChatMessage)).scalars())


def _fake_chat_provider(*, text: str | None = None, exc: Exception | None = None):
    calls: list[tuple[dict, str]] = []

    def chat(context, user_message):
        calls.append((context, user_message))
        if exc is not None:
            raise exc
        return text

    return SimpleNamespace(name="deepseek", enabled=True, chat=chat), calls


def test_post_chat_returns_503_without_provider_key(client) -> None:
    with db_module.SessionLocal() as db:
        strategy_id = _seed_strategy(db).id

    response = client.post(
        "/api/v1/copilot/chat",
        json={"resource": "strategy", "id": str(strategy_id), "message": "该停了吗？"},
    )

    assert response.status_code == 503
    assert "未启用" in response.json()["detail"]


def test_post_chat_enqueues_202(client, monkeypatch) -> None:
    captured: list[tuple[str, str, str]] = []

    def delay(resource: str, resource_id: str, message: str) -> None:
        captured.append((resource, resource_id, message))

    monkeypatch.setattr("services.worker.tasks.run_chat_task", SimpleNamespace(delay=delay))
    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    try:
        with db_module.SessionLocal() as db:
            strategy_id = _seed_strategy(db).id
        response = client.post(
            "/api/v1/copilot/chat",
            json={"resource": "strategy", "id": str(strategy_id), "message": "  下一步验证什么？ "},
        )
        assert response.status_code == 202
        assert response.json() == {"status": "queued"}
        assert captured == [("strategy", str(strategy_id), "下一步验证什么？")]
    finally:
        get_settings.cache_clear()


def test_get_chat_returns_empty_for_unknown_strategy(client) -> None:
    response = client.get(f"/api/v1/copilot/chat?strategy_id={uuid4()}")
    assert response.status_code == 200
    assert response.json() == []


def test_post_chat_returns_404_and_422(client, monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    try:
        missing = client.post(
            "/api/v1/copilot/chat",
            json={"resource": "strategy", "id": str(uuid4()), "message": "该停了吗？"},
        )
        invalid = client.post(
            "/api/v1/copilot/chat",
            json={"resource": "note", "id": str(uuid4()), "message": "该停了吗？"},
        )
        assert missing.status_code == 404
        assert invalid.status_code == 422
    finally:
        get_settings.cache_clear()


def test_execute_chat_records_done_row(db_session, monkeypatch) -> None:
    provider, calls = _fake_chat_provider(text="先补验证，再决定是否继续。")
    monkeypatch.setattr("services.worker.tasks.copilot.get_provider", lambda: provider)
    with db_session() as db:
        strategy_id = _seed_strategy(db).id

    result = execute_chat("strategy", str(strategy_id), "下一步验证什么？")

    assert result["status"] == "done"
    rows = _chat_rows(db_session)
    assert len(rows) == 1
    assert rows[0].status == CopilotChatStatus.DONE
    assert rows[0].assistant_message == "先补验证，再决定是否继续。"
    assert rows[0].user_message == "下一步验证什么？"
    assert calls[0][0]["total_trials"] == 0
    assert "code" not in calls[0][0]


def test_execute_chat_records_provider_failure(db_session, monkeypatch) -> None:
    provider, _calls = _fake_chat_provider(exc=CopilotProviderError("无法连接 DeepSeek"))
    monkeypatch.setattr("services.worker.tasks.copilot.get_provider", lambda: provider)
    with db_session() as db:
        strategy_id = _seed_strategy(db).id

    result = execute_chat("strategy", str(strategy_id), "该停了吗？")

    assert result["status"] == "failed"
    rows = _chat_rows(db_session)
    assert rows[0].status == CopilotChatStatus.FAILED
    assert "无法连接" in (rows[0].error or "")
