"""P6 acceptance: workspace isolation (P6A) and the fail-closed live guard (P6B/C).

Isolation: another workspace must not read, list or mutate this workspace's
strategies, and the attempt is audited. Live: activation stays blocked without
explicit authorization, a configured broker, evidence and capital caps — old
success can never activate live, and the guard refuses before any network call.
"""

from __future__ import annotations

import uuid

from services.api.models import DEFAULT_WORKSPACE_ID, Workspace


def _other_workspace(client) -> str:
    from services.api import db as db_module

    db = db_module.SessionLocal()
    try:
        row = Workspace(slug=f"ws-{uuid.uuid4().hex[:6]}", name="另一个工作区")
        db.add(row)
        db.commit()
        return row.slug
    finally:
        db.close()


def test_cross_workspace_read_is_denied_and_audited(client):
    created = client.post("/api/v1/strategies", json={"name": "隔离验证"}).json()
    other = _other_workspace(client)

    denied = client.get(f"/api/v1/strategies/{created['id']}", headers={"X-Workspace-Id": other})
    assert denied.status_code == 404
    assert "跨工作区" in denied.json()["detail"]

    # 列表不泄漏
    listed = client.get("/api/v1/strategies", headers={"X-Workspace-Id": other}).json()
    assert all(item["id"] != created["id"] for item in listed["items"])

    # 拒绝被审计
    from sqlalchemy import select

    from services.api import db as db_module
    from services.api.models import AuditLog

    db = db_module.SessionLocal()
    try:
        rows = db.scalars(
            select(AuditLog).where(AuditLog.action == "strategy_access_forbidden")
        ).all()
        assert rows, "跨工作区访问必须留审计记录"
    finally:
        db.close()


def test_cross_workspace_write_is_denied(client):
    created = client.post("/api/v1/strategies", json={"name": "隔离写入"}).json()
    other = _other_workspace(client)
    patched = client.patch(
        f"/api/v1/strategies/{created['id']}",
        json={"name": "被改名了"},
        headers={"X-Workspace-Id": other},
    )
    assert patched.status_code == 404
    deleted = client.delete(
        f"/api/v1/strategies/{created['id']}", headers={"X-Workspace-Id": other}
    )
    assert deleted.status_code == 404
    still = client.get(f"/api/v1/strategies/{created['id']}").json()
    assert still["name"] == "隔离写入"


def test_unknown_explicit_workspace_is_refused(client):
    res = client.get("/api/v1/strategies", headers={"X-Workspace-Id": "no-such-ws"})
    assert res.status_code == 404
    assert "不存在" in res.json()["detail"]


def test_default_workspace_is_provisioned(client):
    created = client.post("/api/v1/strategies", json={"name": "默认工作区"}).json()
    assert created["id"]
    from sqlalchemy import select

    from services.api import db as db_module
    from services.api.models import Strategy

    db = db_module.SessionLocal()
    try:
        row = db.scalars(select(Strategy).where(Strategy.id == uuid.UUID(created["id"]))).one()
        assert row.workspace_id == DEFAULT_WORKSPACE_ID
    finally:
        db.close()


def test_live_activation_is_fail_closed_without_authorization(client, monkeypatch):
    strategy = client.post("/api/v1/strategies", json={"name": "实盘守卫"}).json()

    readiness = client.get(f"/api/v1/live/readiness?strategy_id={strategy['id']}")
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["ready"] is False

    blocked = client.post(
        "/api/v1/live/activate",
        json={"strategy_id": strategy["id"], "authorization": "", "capital_cap": 10_000},
    )
    assert blocked.status_code in (401, 403, 409)
    detail = str(blocked.json()["detail"])
    assert "授权" in detail or "authorization" in detail.lower()


def test_live_activation_requires_broker_and_evidence_even_with_token(client, monkeypatch):
    monkeypatch.setenv("STREET_LIVE_AUTHORIZATION_TOKEN", "test-token")
    monkeypatch.setenv("STREET_LIVE_CAPITAL_CAP", "50000")
    from services.api.settings import get_settings

    get_settings.cache_clear()
    strategy = client.post("/api/v1/strategies", json={"name": "实盘守卫2"}).json()

    res = client.post(
        "/api/v1/live/activate",
        json={"strategy_id": strategy["id"], "authorization": "test-token", "capital_cap": 10_000},
    )
    # 即使授权正确，券商未接入/证据不足也必须拒绝（不冒充通过）。
    assert res.status_code in (403, 409)
    detail = str(res.json()["detail"])
    assert "券商" in detail or "broker" in detail.lower() or "证据" in detail or "验证" in detail
    get_settings.cache_clear()


def test_emergency_stop_is_independent_and_idempotent(client):
    first = client.post("/api/v1/live/emergency-stop")
    second = client.post("/api/v1/live/emergency-stop")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["stopped"] is True
    assert second.json()["stopped"] is True
