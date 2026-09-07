from uuid import UUID


def test_syntax_rejects_empty_and_bad_python(client):
    empty = client.post("/api/v1/code/syntax", json={"code": "   "})
    assert empty.status_code == 200, empty.text
    assert empty.json()["ok"] is False
    assert empty.json()["line"] == 1

    bad = client.post("/api/v1/code/syntax", json={"code": "def broken(\n"})
    assert bad.status_code == 200, bad.text
    body = bad.json()
    assert body["ok"] is False
    assert body["line"] is not None

    ok = client.post("/api/v1/code/syntax", json={"code": "class Algo:\n    pass\n"})
    assert ok.json()["ok"] is True
    assert ok.json()["message"] is None


def test_research_note_prefills_hypothesis_and_rejects_foreign_backtest(client):
    strategy = client.post(
        "/api/v1/strategies",
        json={"name": "note-src", "config": {"hypothesis": "价格在均线之上应持有风险资产。"}},
    ).json()
    other = client.post("/api/v1/strategies", json={"name": "note-other"}).json()

    # Seed the foreign backtest via ORM: the API create path validates market
    # data coverage, which CI runners lack (data/ is gitignored).
    from datetime import date
    from uuid import uuid4

    from services.api import db as db_module
    from services.api.models import Backtest, BacktestStatus, StrategyVersion

    db = db_module.SessionLocal()
    try:
        version = db.get(StrategyVersion, UUID(other["latest_version"]["id"]))
        assert version is not None
        backtest = Backtest(
            id=uuid4(),
            strategy_version_id=version.id,
            start_date=date(2018, 1, 1),
            end_date=date(2020, 12, 31),
            status=BacktestStatus.COMPLETED,
            universe_snapshot=[],
        )
        db.add(backtest)
        foreign_bt_id = str(backtest.id)
    finally:
        db.commit()
        db.close()

    created = client.post(
        "/api/v1/research-notes",
        json={"strategy_id": strategy["id"]},
    )
    assert created.status_code == 201, created.text
    note = created.json()
    assert note["title"] == "note-src 研究笔记"
    assert note["hypothesis"] == "价格在均线之上应持有风险资产。"
    assert note["method"] == ""
    assert note["conclusion"] == ""
    assert note["failure_modes"] == ""

    conflict = client.post(
        "/api/v1/research-notes",
        json={"strategy_id": strategy["id"], "backtest_id": foreign_bt_id},
    )
    assert conflict.status_code == 409, conflict.text
    assert "不属于该策略" in conflict.json()["detail"]

    listed = client.get(f"/api/v1/research-notes?strategy_id={strategy['id']}")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    patched = client.patch(
        f"/api/v1/research-notes/{note['id']}",
        json={
            "title": " ",
        },
    )
    assert patched.status_code == 400

    saved = client.patch(
        f"/api/v1/research-notes/{note['id']}",
        json={
            "title": "失效模式",
            "method": "全样本回测 + DSR",
            "conclusion": "夏普过低，不晋升。",
            "failure_modes": "趋势反转后仍持有。",
            "strategy_version_id": strategy["latest_version"]["id"],
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["title"] == "失效模式"
    assert body["strategy_version_id"] == strategy["latest_version"]["id"]
    UUID(body["id"])

    missing = client.get("/api/v1/research-notes/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404

    deleted = client.delete(f"/api/v1/research-notes/{note['id']}")
    assert deleted.status_code == 204
    gone = client.get(f"/api/v1/research-notes/{note['id']}")
    assert gone.status_code == 404
