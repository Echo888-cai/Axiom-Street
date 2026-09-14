"""P2.1 acceptance: versioned rules schema + stale-draft conflict detection.

Covers "过期草稿不能覆盖新版本" (409), config schema/range validation (422)
and the shared code hash used by client/server conflict checks.
"""

from __future__ import annotations

import pytest


def _strategy_with_versions(client) -> tuple[dict, dict]:
    """Create a strategy and return (strategy, current latest version)."""
    created = client.post("/api/v1/strategies", json={"name": "P21 冲突检测"}).json()
    v1 = created["latest_version"]
    v2 = client.post(
        f"/api/v1/strategies/{created['id']}/versions",
        json={
            "code": v1["code"] + "\n# second\n",
            "config": v1["config"],
            "commit_message": "v2",
        },
    )
    assert v2.status_code == 201
    return created, v2.json()


def test_create_with_current_source_is_allowed(client):
    strategy, v2 = _strategy_with_versions(client)
    res = client.post(
        f"/api/v1/strategies/{strategy['id']}/versions",
        json={
            "code": v2["code"] + "\n# third\n",
            "config": v2["config"],
            "source_version_id": v2["id"],
        },
    )
    assert res.status_code == 201
    assert res.json()["version"] == 3


def test_stale_draft_version_conflict(client):
    strategy, v2 = _strategy_with_versions(client)
    # 草稿基于 v1，但最新已是 v2 → 拒绝覆盖。
    res = client.post(
        f"/api/v1/strategies/{strategy['id']}/versions",
        json={
            "code": "class A:\n    pass\n",
            "config": {},
            "source_version_id": strategy["latest_version"]["id"],
        },
    )
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["code"] == "draft_stale"


def test_stale_draft_hash_conflict(client):
    strategy, v2 = _strategy_with_versions(client)
    res = client.post(
        f"/api/v1/strategies/{strategy['id']}/versions",
        json={
            "code": v2["code"] + "\n# edited\n",
            "config": v2["config"],
            "source_version_id": v2["id"],
            "source_code_hash": "deadbeef",  # 与源版本代码哈希不符
        },
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "draft_stale_code"


def test_source_version_of_another_strategy_conflict(client):
    a = client.post("/api/v1/strategies", json={"name": "A"}).json()
    b = client.post("/api/v1/strategies", json={"name": "B"}).json()
    res = client.post(
        f"/api/v1/strategies/{b['id']}/versions",
        json={
            "code": b["latest_version"]["code"] + "\n# x\n",
            "config": b["latest_version"]["config"],
            "source_version_id": a["latest_version"]["id"],
        },
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "draft_stale"


def test_builder_config_range_rejected(client):
    created = client.post("/api/v1/strategies", json={"name": "越界配置"}).json()
    config = dict(created["latest_version"]["config"])
    config["signal"]["lookback_period"] = 10  # 低于 20
    res = client.post(
        f"/api/v1/strategies/{created['id']}/versions",
        json={"code": created["latest_version"]["code"], "config": config},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "builder_config_invalid"


def test_future_schema_version_rejected(client):
    created = client.post("/api/v1/strategies", json={"name": "未来版本"}).json()
    config = dict(created["latest_version"]["config"])
    config["schema_version"] = 99
    res = client.post(
        f"/api/v1/strategies/{created['id']}/versions",
        json={"code": created["latest_version"]["code"], "config": config},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "builder_config_invalid"


def test_normalize_adds_schema_version_and_keeps_rules():
    from quant.strategy_sdk import normalize_builder_config
    from quant.strategy_sdk.schema import BUILDER_SCHEMA_VERSION

    cfg = normalize_builder_config({})
    assert cfg["schema_version"] == BUILDER_SCHEMA_VERSION

    trend = {
        "signal": {"lookback_period": 200},
        "position_sizing": {"target_weight": 1.0},
        "execution": {"slippage_bps": 5},
    }
    out = normalize_builder_config(trend)
    assert out["schema_version"] == BUILDER_SCHEMA_VERSION

    with pytest.raises(ValueError):
        normalize_builder_config({"signal": {"lookback_period": 3}})
    # 仓位 0.5 → 50% 在 1–100% 区间内，应通过；2.0 → 200% 超限被拒。
    assert normalize_builder_config({"position_sizing": {"target_weight": 0.5}})["schema_version"]
    with pytest.raises(ValueError):
        normalize_builder_config({"position_sizing": {"target_weight": 2.0}})
    with pytest.raises(ValueError):
        normalize_builder_config({"execution": {"slippage_bps": 500}})
    with pytest.raises(ValueError):
        normalize_builder_config({"schema_version": 99})


def test_strategy_code_hash_is_stable_sha256():
    from quant.strategy_sdk import strategy_code_hash

    h1 = strategy_code_hash("class A:\n    pass\n")
    assert h1 == strategy_code_hash("class A:\n    pass\n")
    assert h1 != strategy_code_hash("class A:\n    pass\n\n")
    assert len(h1) == 64
