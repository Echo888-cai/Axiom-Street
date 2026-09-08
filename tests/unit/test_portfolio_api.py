"""Portfolio attribution HTTP contract tests (E8-1)."""

from __future__ import annotations

import pytest


def _create_strategy(client, name: str) -> str:
    response = client.post("/api/v1/strategies", json={"name": name, "benchmark": "SPY"})
    assert response.status_code == 201
    return response.json()["id"]


def _create_portfolio(client) -> str:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": "Balanced research", "base_currency": "USD", "initial_capital": 100000},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_portfolio_attribution_uses_server_owned_weights(client) -> None:
    first = _create_strategy(client, "Trend allocation")
    second = _create_strategy(client, "Carry allocation")
    portfolio_id = _create_portfolio(client)
    for strategy_id, weight in ((first, 0.6), (second, 0.4)):
        allocation = client.post(
            f"/api/v1/portfolios/{portfolio_id}/allocations",
            json={
                "strategy_id": strategy_id,
                "weight": weight,
                "effective_from": "2026-01-01",
            },
        )
        assert allocation.status_code == 201, allocation.text

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/attribution",
        json={
            "as_of": "2026-09-08",
            "returns": [
                {
                    "strategy_id": first,
                    "strategy_return": 0.10,
                    "benchmark_return": 0.05,
                    "weight": 0.1,
                },
                {
                    "strategy_id": second,
                    "strategy_return": 0.00,
                    "benchmark_return": 0.02,
                    "weight": 0.9,
                },
            ],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["portfolio_return"] == 0.06
    assert body["active_return"] == pytest.approx(0.025)
    assert body["inputs"]["weights"][first] == 0.6
    assert body["inputs"]["weights"][second] == 0.4

    listed = client.get(f"/api/v1/portfolios/{portfolio_id}/attribution")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_portfolio_api_rejects_unknown_strategy_and_duplicate_snapshot(client) -> None:
    portfolio_id = _create_portfolio(client)
    missing = client.post(
        f"/api/v1/portfolios/{portfolio_id}/allocations",
        json={
            "strategy_id": "11111111-1111-4111-8111-111111111111",
            "weight": 1,
            "effective_from": "2026-01-01",
        },
    )
    assert missing.status_code == 404

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/attribution",
        json={
            "as_of": "2026-09-08",
            "returns": [
                {
                    "strategy_id": "11111111-1111-4111-8111-111111111111",
                    "strategy_return": 0,
                    "benchmark_return": 0,
                }
            ],
        },
    )
    assert response.status_code == 409
