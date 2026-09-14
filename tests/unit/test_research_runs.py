"""P4.3 acceptance: bounded research runs with persisted, idempotent, checkpointed
steps. Restart resumes from the checkpoint; budgets stop new work; pause/resume
and cancel have explicit semantics.
"""

from __future__ import annotations


def _create(client, **extra) -> dict:
    body = {"goal": "SPY 200 日均线，滑点 5 bps", **extra}
    res = client.post("/api/v1/research-runs", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_run_persists_steps_and_completes(client):
    run = _create(client)
    assert run["status"] == "RUNNING"
    assert [s["name"] for s in run["steps"]] == ["draft_rules", "compile", "review", "summarize"]
    assert all(s["status"] == "PENDING" for s in run["steps"])
    assert run["checkpoint"]["next_index"] == 0

    for _ in range(4):
        run = client.post(f"/api/v1/research-runs/{run['id']}/step").json()
    assert run["status"] == "COMPLETED"
    assert run["spent"]["steps"] == 4
    outputs = run["checkpoint"]["outputs"]
    assert outputs["draft_rules"]["draft"]["lookback"] == 200
    assert "class Spy200DmaAlgorithm" in outputs["compile"]["code"]
    assert outputs["review"]["approvable"] is True
    assert outputs["summarize"]["citations"]["review_approvable"] is True


def test_restart_resumes_from_checkpoint_without_duplicating_steps(client):
    run = _create(client)
    client.post(f"/api/v1/research-runs/{run['id']}/step")
    client.post(f"/api/v1/research-runs/{run['id']}/step")
    mid = client.get(f"/api/v1/research-runs/{run['id']}").json()
    assert mid["checkpoint"]["next_index"] == 2
    assert mid["spent"]["steps"] == 2

    # “重启”后继续：从检查点的下一步继续，不重复已完成步骤的副作用。
    resumed = client.post(f"/api/v1/research-runs/{run['id']}/step").json()
    assert resumed["checkpoint"]["next_index"] == 3
    assert resumed["spent"]["steps"] == 3
    assert resumed["steps"][2]["name"] == "review"


def test_budget_exhaustion_pauses_instead_of_overspending(client):
    run = _create(client, budget={"max_steps": 2, "max_lean_runs": 0, "max_minutes": 30})
    client.post(f"/api/v1/research-runs/{run['id']}/step")
    client.post(f"/api/v1/research-runs/{run['id']}/step")
    blocked = client.post(f"/api/v1/research-runs/{run['id']}/step").json()
    assert blocked["status"] == "PAUSED"
    assert "预算" in (blocked["error"] or "")
    assert blocked["spent"]["steps"] == 2

    # 暂停状态下不能推进；恢复后仍受预算约束（预算未提高 → 仍被拦停）。
    conflict = client.post(f"/api/v1/research-runs/{run['id']}/step")
    assert conflict.status_code == 409
    resumed = client.post(f"/api/v1/research-runs/{run['id']}/resume").json()
    assert resumed["status"] == "RUNNING"
    after = client.post(f"/api/v1/research-runs/{run['id']}/step").json()
    assert after["status"] == "PAUSED"
    assert after["checkpoint"]["next_index"] == 2  # 预算门控：不超支


def test_pause_resume_and_cancel_semantics(client):
    run = _create(client)
    paused = client.post(f"/api/v1/research-runs/{run['id']}/pause").json()
    assert paused["status"] == "PAUSED"
    blocked = client.post(f"/api/v1/research-runs/{run['id']}/step")
    assert blocked.status_code == 409

    resumed = client.post(f"/api/v1/research-runs/{run['id']}/resume").json()
    assert resumed["status"] == "RUNNING"

    cancelled = client.post(f"/api/v1/research-runs/{run['id']}/cancel").json()
    assert cancelled["status"] == "CANCELLED"
    terminal = client.post(f"/api/v1/research-runs/{run['id']}/step")
    assert terminal.status_code == 409


def test_run_is_idempotent_when_advancing_a_completed_step(client, monkeypatch):
    from uuid import UUID

    from services.api import db as db_module
    from services.api.models import ResearchRun, ResearchStepStatus

    run = _create(client)
    client.post(f"/api/v1/research-runs/{run['id']}/step")
    run_uuid = UUID(run["id"])
    db = db_module.SessionLocal()
    try:
        # 人为把 checkpoint 退回去模拟“重复投递已完成的步骤”
        row = db.get(ResearchRun, run_uuid)
        row.checkpoint = {**row.checkpoint, "next_index": 0}
        db.commit()
    finally:
        db.close()

    replayed = client.post(f"/api/v1/research-runs/{run['id']}/step").json()
    # 不重复副作用：步数不增加，只推进检查点。
    assert replayed["spent"]["steps"] == 1
    assert replayed["checkpoint"]["next_index"] == 1
    assert replayed["steps"][0]["status"] == ResearchStepStatus.COMPLETED.value
