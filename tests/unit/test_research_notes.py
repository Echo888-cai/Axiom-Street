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
    foreign_bt = client.post(
        "/api/v1/backtests",
        json={
            "strategy_version_id": other["latest_version"]["id"],
            "start_date": "2018-01-01",
            "end_date": "2020-12-31",
        },
    ).json()

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
        json={"strategy_id": strategy["id"], "backtest_id": foreign_bt["id"]},
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
