def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["service"] == "api"
    assert body["status"] in {"ok", "degraded", "down"}
    assert "checks" in body


def test_strategy_list_pagination_search_and_status_filter(client):
    for i in range(5):
        res = client.post(
            "/api/v1/strategies",
            json={"name": f"Trend {i}", "description": "momentum"},
        )
        assert res.status_code == 201, res.text
    res = client.post(
        "/api/v1/strategies",
        json={"name": "Value fund", "description": "mean reversion"},
    )
    assert res.status_code == 201, res.text

    page1 = client.get("/api/v1/strategies?limit=2&offset=0").json()
    assert page1["total"] == 6
    assert page1["limit"] == 2
    assert page1["offset"] == 0
    assert len(page1["items"]) == 2
    page3 = client.get("/api/v1/strategies?limit=2&offset=4").json()
    assert page3["total"] == 6
    assert len(page3["items"]) == 2
    assert {item["id"] for item in page1["items"]}.isdisjoint(
        {item["id"] for item in page3["items"]}
    )
    beyond = client.get("/api/v1/strategies?limit=2&offset=6").json()
    assert beyond["total"] == 6
    assert beyond["items"] == []

    search = client.get("/api/v1/strategies?q=trend").json()
    assert search["total"] == 5
    assert all("Trend" in item["name"] for item in search["items"])
    desc_search = client.get("/api/v1/strategies?q=MEAN").json()
    assert desc_search["total"] == 1
    assert desc_search["items"][0]["name"] == "Value fund"

    drafts = client.get("/api/v1/strategies?status=DRAFT").json()
    assert drafts["total"] == 6
    validated = client.get("/api/v1/strategies?status=VALIDATED").json()
    assert validated["total"] == 0
    assert validated["items"] == []
    bad = client.get("/api/v1/strategies?status=NOPE")
    assert bad.status_code == 422


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
