"""P3.1 acceptance: data catalog + separate price/dividend/split entitlement probes.

Every failure mode must map to an actionable reason (missing key, 401, 403,
429, no data, network) instead of a generic "data unavailable".
"""

from __future__ import annotations

import json
from pathlib import Path


def _write_snapshot(root: Path, key: str, **manifest_extra) -> None:
    snap = root / "snapshots" / key
    (snap / "market" / "equities" / "US" / "daily").mkdir(parents=True, exist_ok=True)
    (snap / "market" / "equities" / "US" / "daily" / "SPY.parquet").write_bytes(b"x")
    manifest = {
        "snapshot_key": key,
        "created_at": "2026-09-14T00:00:00+00:00",
        "symbols": ["SPY"],
        "exchange_timezone": "America/New_York",
        "provider_capabilities": {"dividends": True, "splits": True, "ohlcv": True},
        "corporate_actions_verified": True,
        "quality_report": {"issues": []},
    }
    manifest.update(manifest_extra)
    (snap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_catalog_lists_snapshot_facts_lineage_and_gaps(tmp_path):
    from quant.data.catalog import build_data_catalog

    (tmp_path / "manifest.json").write_text(
        json.dumps({"symbols": ["SPY"], "source": "polygon"}), encoding="utf-8"
    )
    _write_snapshot(
        tmp_path,
        "spy-20260101",
        created_at="2026-01-01T00:00:00+00:00",
        prior_snapshot_key="spy-20251231",
    )
    _write_snapshot(
        tmp_path,
        "spy-20251231",
        created_at="2025-12-31T00:00:00+00:00",
        quality_report={"issues": [{"rule": "gap", "severity": "warn"}]},
    )

    catalog = build_data_catalog(tmp_path)
    assert catalog["snapshot_count"] == 2
    newest = catalog["snapshots"][0]
    assert newest["snapshot_key"] == "spy-20260101"
    assert newest["frequency"] == "daily"
    assert newest["timezone"] == "America/New_York"
    assert newest["adjustment"] == "adjusted"
    assert newest["prior_snapshot_key"] == "spy-20251231"
    assert newest["corporate_actions_verified"] is True
    older = catalog["snapshots"][1]
    assert older["gaps"] and older["gaps"][0]["rule"] == "gap"


class _Resp:
    def __init__(self, status_code: int, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_probe_polygon_separates_price_dividends_splits_entitlement():
    from quant.data.catalog import probe_capabilities

    def get(url: str, params=None):
        if "/v2/aggs" in url:
            return _Resp(200, {"results": [{"t": 1}]})
        if "/v3/reference/dividends" in url:
            return _Resp(403, text="not entitled")
        if "/v3/reference/splits" in url:
            return _Resp(429, text="slow down")
        return _Resp(404)

    out = probe_capabilities(provider="polygon", api_key="k", get=get, symbol="SPY")
    caps = out["capabilities"]
    assert caps["price"]["code"] == "ok"
    assert caps["dividends"]["code"] == "forbidden"
    assert "订阅" in caps["dividends"]["message"]
    assert caps["splits"]["code"] == "rate_limited"
    assert "RPS" in caps["splits"]["message"]


def test_probe_polygon_missing_key_and_auth_failure():
    from quant.data.catalog import probe_capabilities

    missing = probe_capabilities(
        provider="polygon", api_key="", get=lambda *a, **k: _Resp(200, {"results": [1]})
    )
    assert missing["capabilities"]["price"]["code"] == "missing_key"

    def get_401(url: str, params=None):
        return _Resp(401, text="bad key")

    bad = probe_capabilities(provider="polygon", api_key="k", get=get_401)
    assert bad["capabilities"]["price"]["code"] == "auth_failed"
    assert "Key" in bad["capabilities"]["price"]["message"]


def test_probe_declares_stooq_corporate_action_gap():
    from quant.data.catalog import probe_capabilities

    out = probe_capabilities(provider="stooq", get=lambda *a, **k: _Resp(200, text="Date,Open"))
    caps = out["capabilities"]
    assert caps["price"]["code"] == "ok"
    assert caps["dividends"]["code"] == "not_supported"
    assert "不提供此数据集" in caps["dividends"]["message"]


def test_probe_network_error_is_actionable():
    from quant.data.catalog import probe_capabilities

    def boom(*_a, **_k):
        raise OSError("connection refused")

    out = probe_capabilities(provider="yfinance", get=boom)
    assert out["capabilities"]["price"]["code"] == "network_error"


def test_catalog_and_probe_endpoints(client, monkeypatch):
    status = client.get("/api/v1/data/catalog")
    assert status.status_code == 200, status.text
    assert "snapshots" in status.json()

    probe = client.post(
        "/api/v1/data/capabilities/probe",
        json={"provider": "stooq", "symbol": "SPY"},
    )
    # 真机探测可能因网络不可达而失败，但必须返回结构化、可行动的原因码。
    assert probe.status_code == 200, probe.text
    body = probe.json()
    assert set(body["capabilities"]) == {"price", "dividends", "splits"}
    assert body["capabilities"]["price"]["code"] in {
        "ok",
        "network_error",
        "rate_limited",
        "unknown_error",
    }
    assert body["capabilities"]["price"]["message"]
