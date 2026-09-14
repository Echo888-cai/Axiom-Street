"""P3.1 data catalog: one place to see source, coverage, frequency, timezone,
adjustment, gaps and declared capabilities, plus a live per-capability probe.

The catalog is a read-only projection over the manifest, the snapshot folders
and (when available) the snapshot ledger. The probe checks price, dividend and
split access *separately* and returns actionable reasons — `missing_key`,
`auth_failed`, `forbidden`, `rate_limited`, `no_data`, `network_error` — so an
operator can fix entitlement/keys instead of guessing at "data unavailable".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from quant.data.manifest import load_manifest
from quant.data.symbols import as_symbol_list
from quant.data.types import CAPABILITIES_BY_SOURCE

_SNAPSHOTS_DIR = "snapshots"

# 可行动原因码：每一种都对应一个操作（补 Key / 申请权限 / 等配额 / 换源）。
REASON_MESSAGES = {
    "missing_key": "缺少 API Key：配置对应环境变量后重试。",
    "auth_failed": "认证失败（401）：检查 Key 是否有效或已过期。",
    "forbidden": "无权限（403）：当前订阅不包含该数据集，需要升级或申请授权。",
    "rate_limited": "触发限流（429）：降低出站 RPS 或稍后重试。",
    "no_data": "该标的在所选区间没有数据：检查代码/交易所/区间。",
    "network_error": "网络或服务不可达：检查出站网络与供应商状态页。",
    "not_supported": "该数据源不提供此数据集：需要换用具备该权限的数据源（如 Polygon）。",
    "unknown_error": "供应商返回未预期错误：查看原始状态码与消息。",
    "ok": "权限正常。",
}


def _reason(code: str, detail: str = "") -> dict[str, str]:
    return {
        "code": code,
        "message": REASON_MESSAGES.get(code, REASON_MESSAGES["unknown_error"]),
        "detail": detail,
    }


def _classify_status(status_code: int) -> str:
    if status_code == 401:
        return "auth_failed"
    if status_code == 403:
        return "forbidden"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 400:
        return "unknown_error"
    return "ok"


def snapshot_catalog_entry(snapshot_dir: Path) -> dict[str, Any]:
    """Describe one immutable snapshot folder (coverage/frequency/tz/adjustment/gaps)."""
    manifest = load_manifest(snapshot_dir)
    quality = manifest.get("quality_report") or {}
    symbols = manifest.get("symbols")
    if not symbols:
        raw = manifest.get("symbol")
        symbols = as_symbol_list(raw) if raw else []
    capabilities = manifest.get("provider_capabilities") or {}
    return {
        "snapshot_key": manifest.get("snapshot_key") or snapshot_dir.name,
        "created_at": manifest.get("created_at"),
        "prior_snapshot_key": manifest.get("prior_snapshot_key"),
        "ingest_mode": manifest.get("ingest_mode"),
        "symbols": symbols,
        "frequency": "daily",
        "timezone": manifest.get("exchange_timezone") or "America/New_York",
        "adjustment": "adjusted",
        "range": {"start": manifest.get("start"), "end": manifest.get("end")},
        "row_count": manifest.get("rows"),
        "providers": manifest.get("providers"),
        "corporate_actions_verified": bool(manifest.get("corporate_actions_verified")),
        "capabilities": capabilities,
        "gaps": quality.get("issues") or [],
        "quality_checked_at": quality.get("checked_at"),
        "content_sha256": manifest.get("sha256") or manifest.get("content_sha256"),
    }


def build_data_catalog(data_root: Path) -> dict[str, Any]:
    """Current manifest facts + every retained snapshot, newest first."""
    root = Path(data_root)
    current = load_manifest(root)
    snapshots: list[dict[str, Any]] = []
    snap_dir = root / _SNAPSHOTS_DIR
    if snap_dir.is_dir():
        for child in sorted(snap_dir.iterdir()):
            if child.is_dir() and (child / "manifest.json").exists():
                snapshots.append(snapshot_catalog_entry(child))
    snapshots.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)

    declared_source = current.get("source")
    providers = current.get("providers") or {}
    active = providers.get("active") if isinstance(providers, dict) else None
    declared_caps = None
    for candidate in (declared_source, str(active or "").split()[0] if active else None):
        if candidate and candidate in CAPABILITIES_BY_SOURCE:
            caps = CAPABILITIES_BY_SOURCE[candidate]
            declared_caps = {
                "ohlcv": caps.ohlcv,
                "dividends": caps.dividends,
                "splits": caps.splits,
                "point_in_time": caps.point_in_time,
            }
            break

    return {
        "data_root": str(root),
        "current": snapshot_catalog_entry(root) if current else None,
        "declared_capabilities": declared_caps,
        "snapshots": snapshots,
        "snapshot_count": len(snapshots),
    }


def probe_capabilities(
    *,
    provider: str,
    symbol: str = "SPY",
    start: str = "2024-01-01",
    end: str = "2024-03-01",
    api_key: str | None = None,
    get: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Probe price / dividends / splits entitlement separately.

    ``get`` is an injectable HTTP getter (tests pass a fake; production omits it
    and a short-lived httpx client is used). The probe never writes snapshots and
    never echoes the key.
    """
    provider = (provider or "auto").strip().lower()
    if provider == "auto":
        provider = "yfinance"
    if provider not in {"polygon", "yfinance", "stooq"}:
        return {
            "provider": provider,
            "symbol": symbol,
            "capabilities": {
                "price": _reason("unknown_error", f"未知数据源 {provider}"),
                "dividends": _reason("unknown_error", f"未知数据源 {provider}"),
                "splits": _reason("unknown_error", f"未知数据源 {provider}"),
            },
        }

    if get is None:
        import httpx

        client = httpx.Client(timeout=15.0, follow_redirects=True)
        get = client.get
        close = client.close
    else:
        close = None

    try:
        if provider == "polygon":
            result = _probe_polygon(get, symbol, start, end, api_key)
        else:
            result = _probe_declared(provider, get, symbol, start, end)
    finally:
        if close is not None:
            close()
    result["provider"] = provider
    result["symbol"] = symbol
    return result


def _probe_polygon(
    get: Callable[..., Any], symbol: str, start: str, end: str, api_key: str | None
) -> dict[str, Any]:
    key = api_key
    if not key:
        import os

        key = os.getenv("POLYGON_API_KEY")
    if not key:
        missing = _reason("missing_key", "POLYGON_API_KEY 未设置")
        return {"capabilities": {"price": missing, "dividends": missing, "splits": missing}}

    def call(url: str, params: dict[str, Any]) -> dict[str, str]:
        try:
            resp = get(url, params={**params, "apiKey": key})
        except Exception as exc:  # noqa: BLE001 - 归一化为可行动原因
            return _reason("network_error", str(exc)[:200])
        code = _classify_status(int(getattr(resp, "status_code", 0)))
        if code != "ok":
            return _reason(code, str(getattr(resp, "text", ""))[:200])
        try:
            payload = resp.json()
        except (json.JSONDecodeError, ValueError):
            return _reason("unknown_error", "响应不是合法 JSON")
        if not payload.get("results"):
            return _reason("no_data", "接口可访问但该区间无记录")
        return _reason("ok", f"results={len(payload['results'])}")

    price = call(
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}",
        {"adjusted": "false", "sort": "asc", "limit": 10},
    )
    dividends = call(
        "https://api.polygon.io/v3/reference/dividends",
        {"ticker": symbol, "limit": 5},
    )
    splits = call(
        "https://api.polygon.io/v3/reference/splits",
        {"ticker": symbol, "limit": 5},
    )
    return {"capabilities": {"price": price, "dividends": dividends, "splits": splits}}


def _probe_declared(
    provider: str, get: Callable[..., Any], symbol: str, start: str, end: str
) -> dict[str, Any]:
    """yfinance/stooq declare corporate-action support; probe prices and report
    the declared (not silently assumed) dividends/splits status."""
    caps = CAPABILITIES_BY_SOURCE[provider]
    try:
        if provider == "yfinance":
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            resp = get(url, params={"period1": 0, "period2": 1, "interval": "1d"})
        else:
            url = "https://stooq.com/q/d/l/"
            resp = get(url, params={"s": symbol.lower(), "i": "d"})
    except Exception as exc:  # noqa: BLE001
        price = _reason("network_error", str(exc)[:200])
        return {
            "capabilities": {
                "price": price,
                "dividends": _reason("unknown_error", "价格探测失败，未验证公司行动"),
                "splits": _reason("unknown_error", "价格探测失败，未验证公司行动"),
            }
        }
    code = _classify_status(int(getattr(resp, "status_code", 0)))
    price = _reason(code, f"HTTP {getattr(resp, 'status_code', '?')}")
    corporate = (
        _reason("ok", "数据源声明提供公司行动")
        if caps.corporate_actions
        else _reason("not_supported", f"{provider} 不提供分红/拆分")
    )
    return {"capabilities": {"price": price, "dividends": corporate, "splits": corporate}}
