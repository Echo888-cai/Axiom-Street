"""P2.4 acceptance: unified reports with evidence, provenance and frozen exports.

Covers: note links validation runs and carries evidence/drafted_by; export
freezes the evidence+timestamp so later edits never rewrite an old export;
a third person can trace every input (version, backtest, validation run ids).
"""

from __future__ import annotations


def _strategy(client) -> dict:
    res = client.post("/api/v1/strategies", json={"name": "报告策略"})
    assert res.status_code == 201, res.text
    return res.json()


def _make_backtest(client, strategy: dict) -> dict:
    res = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": strategy["latest_version"]["id"],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "benchmark": "SPY",
            "initial_capital": 100000,
        },
    )
    assert res.status_code in (200, 201), res.text
    return res.json()


def _make_note(client, strategy: dict, **extra) -> dict:
    body = {
        "strategy_id": strategy["id"],
        "strategy_version_id": strategy["latest_version"]["id"],
        "title": "第一篇报告",
        "hypothesis": "动量持续假设",
        "method": "SPY 200DMA 回测 + 验证",
        "conclusion": "样本内支持",
        "failure_modes": "震荡市失效",
        **extra,
    }
    res = client.post("/api/v1/research-notes", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_note_carries_evidence_and_provenance(client):
    strategy = _strategy(client)
    note = _make_note(
        client,
        strategy,
        drafted_by={"hypothesis": "ai", "conclusion": "human"},
        evidence={"items": [{"kind": "version", "id": "x"}], "captured_at": "2026-09-14T00:00:00Z"},
    )
    assert note["drafted_by"] == {"hypothesis": "ai", "conclusion": "human"}
    assert note["evidence"]["items"][0]["kind"] == "version"


def test_export_freezes_evidence_and_isnot_rewritten_by_edits(client, monkeypatch):
    """P2.4 验收：第三人凭导出可找到输入；新研究不悄悄改写旧导出。"""

    strategy = _strategy(client)
    bt = _make_backtest(client, strategy)
    note = _make_note(client, strategy, backtest_id=bt["id"])

    first = client.post(f"/api/v1/research-notes/{note['id']}/export")
    assert first.status_code == 201, first.text
    exported = first.json()
    evidence = exported["payload"]["evidence"]["items"]
    kinds = {item["kind"] for item in evidence}
    assert {"version", "backtest"} <= kinds
    backtest_item = next(item for item in evidence if item["kind"] == "backtest")
    assert backtest_item["id"] == bt["id"]
    assert backtest_item["data_version"] is not None  # 快照可回溯
    assert exported["payload"]["manifest"]["backtest_id"] == bt["id"]

    # 修改笔记内容后，旧导出 payload 保持不变（新导出另起一行）
    client.patch(
        f"/api/v1/research-notes/{note['id']}",
        json={"conclusion": "后来否定了样本内结论"},
    )
    exports = client.get(f"/api/v1/research-notes/{note['id']}/exports").json()
    assert len(exports) == 1
    assert exports[0]["id"] == exported["id"]
    assert exports[0]["payload"]["note"]["conclusion"] == "样本内支持"

    second = client.post(f"/api/v1/research-notes/{note['id']}/export").json()
    assert second["payload"]["note"]["conclusion"] == "后来否定了样本内结论"
    assert second["id"] != exported["id"]


def test_note_links_validation_run(client, monkeypatch):
    from uuid import UUID, uuid4

    from services.api import db as db_module
    from services.api.models import (
        Strategy,
        StrategyVersion,
        ValidationKind,
        ValidationRun,
        ValidationRunStatus,
    )

    strategy = _strategy(client)
    db = db_module.SessionLocal()
    run_id = uuid4()
    try:
        strategy_row = db.get(Strategy, UUID(strategy["id"]))
        assert strategy_row is not None
        row = StrategyVersion(
            strategy_id=strategy_row.id,
            version=99,
            code="x",
            config={},
            created_by="local",
        )
        db.add(row)
        db.flush()
        run = ValidationRun(
            id=run_id,
            strategy_id=strategy_row.id,
            strategy_version_id=row.id,
            kind=ValidationKind.PBO,
            status=ValidationRunStatus.COMPLETED,
            params={},
            result={},
        )
        db.add(run)
        db.commit()
    finally:
        db.close()

    note = _make_note(client, strategy, validation_run_id=str(run_id))
    assert note["validation_run_id"] == str(run_id)
    exported = client.post(f"/api/v1/research-notes/{note['id']}/export").json()
    labels = {item["label"] for item in exported["payload"]["evidence"]["items"]}
    assert "PBO 验证" in labels
