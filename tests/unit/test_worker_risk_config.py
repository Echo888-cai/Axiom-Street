"""Worker risk-limit resolution (Phase 6 WP-1)."""

from __future__ import annotations

import json

import pytest

from services.worker.tasks.risk_config import resolve_risk_config_json


def test_no_block_returns_none() -> None:
    assert resolve_risk_config_json({}) is None
    assert resolve_risk_config_json(None) is None
    assert resolve_risk_config_json({"class_name": "Spy200DmaAlgorithm"}) is None


def test_binding_block_serializes() -> None:
    payload = resolve_risk_config_json({"risk_limits": {"max_position_pct": 0.5}})
    assert payload is not None
    assert json.loads(payload)["max_position_pct"] == 0.5


def test_invalid_block_raises() -> None:
    with pytest.raises(ValueError, match="risk_limits"):
        resolve_risk_config_json({"risk_limits": {"bogus": 1}})


def test_legacy_risk_block_is_ignored() -> None:
    # The old inert `risk` block must NOT gate (equal_weight 1/N trap).
    assert resolve_risk_config_json({"risk": {"max_position_pct": 0.1}}) is None
