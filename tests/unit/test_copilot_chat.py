"""P5-4 guided Copilot chat contract and execution tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.api.models import CopilotChatMessage, CopilotChatStatus
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
