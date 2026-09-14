"""P4.1/P4.2 acceptance: deterministic rule drafts, explicit unsupported
semantics, and a read-only change review that never writes a version and never
widens the Copilot outbound scope.
"""

from __future__ import annotations

import pytest


def test_intent_parse_is_deterministic_without_a_model():
    from services.agent.rules import draft_rules_from_intent

    draft = draft_rules_from_intent("QQQ 100 日均线，持有 80% 仓位，滑点 3 bps")
    assert draft.template == "trend"
    assert draft.symbol == "QQQ"
    assert draft.lookback == 100
    assert draft.position_pct == 80.0
    assert draft.slippage_bps == 3.0
    assert draft.source == "deterministic"
    assert draft.unsupported == []


def test_unsupported_semantics_are_reported_not_silently_implemented():
    from services.agent.rules import draft_rules_from_intent

    draft = draft_rules_from_intent("用 2 倍杠杆做空 SPY，加止损")
    assert "leverage" in draft.unsupported
    assert "short" in draft.unsupported
    assert "stop_loss" in draft.unsupported
    assert any("不支持" in w for w in draft.warnings)
    # 草案仍然可用，但语义不会被偷偷补上
    code, config = __import__("services.agent.rules", fromlist=["x"]).compile_trend_rules(draft)
    assert "SetHoldings" in code
    assert config["risk"]["stop_loss"] is None
    assert config["position_sizing"]["target_weight"] <= 1.0


def test_compile_is_deterministic_and_validates_ranges():
    from services.agent.rules import RuleDraft, compile_trend_rules

    draft = RuleDraft(
        template="trend",
        symbol="SPY",
        lookback=200,
        position_pct=100,
        slippage_bps=5,
        hypothesis="基线",
    )
    code_a, config_a = compile_trend_rules(draft)
    code_b, config_b = compile_trend_rules(draft)
    assert code_a == code_b and config_a == config_b
    assert config_a["schema_version"] >= 1
    assert 'self.AddEquity("SPY",' in code_a

    bad = RuleDraft(
        template="trend",
        symbol="SPY",
        lookback=5,
        position_pct=100,
        slippage_bps=5,
        hypothesis="越界",
    )
    with pytest.raises(ValueError):
        compile_trend_rules(bad)


def test_rule_draft_and_compile_endpoints(client):
    draft = client.post("/api/v1/copilot/rules/draft", json={"text": "SPY 200 日均线"})
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["template"] == "trend" and body["lookback"] == 200

    compiled = client.post(
        "/api/v1/copilot/rules/compile",
        json={"template": "trend", "symbol": "SPY", "lookback": 50, "position_pct": 50},
    )
    assert compiled.status_code == 200, compiled.text
    assert compiled.json()["config"]["position_sizing"]["target_weight"] == 0.5

    rejected = client.post(
        "/api/v1/copilot/rules/compile",
        json={"template": "trend", "symbol": "SPY", "lookback": 5},
    )
    assert rejected.status_code == 422


def test_review_is_read_only_and_flags_real_risks():
    from services.agent.rule_review import review_rule_change

    report = review_rule_change(
        current_code="from AlgorithmImports import *\n",
        proposed_code=(
            "from AlgorithmImports import *\nimport os\nx = self.History(self.spy.Symbol, 5, 0)\n"
        ),
        source_version_id="v1",
        latest_version_id="v2",
    )
    assert report["writes_version"] is False
    assert report["outbound_scope"]["sends_source_code"] is False
    assert report["checks"]["dependencies"]["ok"] is False
    assert report["checks"]["future_data"]["ok"] is False
    assert report["checks"]["version_conflict"]["stale"] is True
    assert report["approvable"] is False
    assert report["diff"]["added"] >= 2


def test_review_endpoint_approves_a_clean_change(client):
    clean = "from AlgorithmImports import *\n\nclass A:\n    pass\n"
    report = client.post(
        "/api/v1/copilot/rules/review",
        json={"current_code": "from AlgorithmImports import *\n", "proposed_code": clean},
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["approvable"] is True
    assert body["writes_version"] is False


def test_review_never_writes_a_strategy_version(client):
    created = client.post("/api/v1/strategies", json={"name": "P42"}).json()
    before = client.get(f"/api/v1/strategies/{created['id']}/versions").json()
    client.post(
        "/api/v1/copilot/rules/review",
        json={
            "current_code": created["latest_version"]["code"],
            "proposed_code": created["latest_version"]["code"] + "\n# proposed\n",
            "source_version_id": created["latest_version"]["id"],
            "latest_version_id": created["latest_version"]["id"],
        },
    )
    after = client.get(f"/api/v1/strategies/{created['id']}/versions").json()
    assert len(after) == len(before)
