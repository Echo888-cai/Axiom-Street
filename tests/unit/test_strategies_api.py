def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["service"] == "api"
    assert body["status"] in {"ok", "degraded", "down"}
    assert "checks" in body


def test_strategy_crud_and_version(client):
    create = client.post(
        "/api/v1/strategies",
        json={
            "name": "SPY 200DMA",
            "description": "Trend",
        },
    )
    assert create.status_code == 201, create.text
    strategy = create.json()
    assert strategy["name"] == "SPY 200DMA"
    assert strategy["latest_version"]["version"] == 1
    assert strategy["family_id"] == strategy["id"]
    assert "Spy200DmaAlgorithm" in strategy["latest_version"]["code"]

    listed = client.get("/api/v1/strategies")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1

    version = client.post(
        f"/api/v1/strategies/{strategy['id']}/versions",
        json={
            "code": strategy["latest_version"]["code"] + "\n# tweak\n",
            "commit_message": "tweak",
            "config": strategy["latest_version"]["config"],
        },
    )
    assert version.status_code == 201
    assert version.json()["version"] == 2


def test_client_cannot_patch_validated(client):
    created = client.post("/api/v1/strategies", json={"name": "guard"}).json()
    res = client.patch(
        f"/api/v1/strategies/{created['id']}",
        json={"status": "VALIDATED"},
    )
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["code"] == "status_transition_forbidden"


def test_client_can_archive(client):
    created = client.post("/api/v1/strategies", json={"name": "arch"}).json()
    res = client.patch(f"/api/v1/strategies/{created['id']}", json={"status": "ARCHIVED"})
    assert res.status_code == 200
    assert res.json()["status"] == "ARCHIVED"


def test_audit_logs_readable(client):
    created = client.post("/api/v1/strategies", json={"name": "audited"}).json()
    res = client.get("/api/v1/audit-logs", params={"object_id": created["id"]})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    assert body["items"][0]["action"] == "Strategy Created"
