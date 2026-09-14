"""P4.1 rule drafts: intent → validated rule draft → deterministic compiled code.

Two hard rules from the plan:

1. **No model required.** Parsing and compilation are deterministic; a model may
   help wording later, but the workspace is fully usable without one.
2. **Never silently widen semantics.** Leverage, shorting, options, stop-loss,
   multi-factor and intraday requests are reported as ``unsupported`` instead of
   being quietly dropped or invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from quant.strategy_sdk.equal_weight import DEFAULT_EQUAL_WEIGHT_UNIVERSE
from quant.strategy_sdk.schema import normalize_builder_config
from quant.strategy_sdk.spy_200dma import DEFAULT_STRATEGY_CODE

_TREND_LOOKBACKS = (50, 100, 200)

# 不支持的语义：必须显式返回，绝不静默补杠杆/做空/退出等定义。
UNSUPPORTED_PATTERNS: tuple[tuple[str, str], ...] = (
    ("leverage", r"杠杆|融资|lever|margin"),
    ("short", r"做空|卖空|short"),
    ("options", r"期权|option|call|put"),
    ("stop_loss", r"止损|stop[\s-]?loss"),
    ("take_profit", r"止盈|take[\s-]?profit"),
    ("intraday", r"日内|分钟|intraday|tick"),
    ("multi_factor", r"因子|factor|多因子"),
    ("futures", r"期货|future"),
    ("crypto", r"加密|比特币|btc|crypto"),
)


@dataclass(frozen=True)
class RuleDraft:
    template: str  # trend | equal_weight
    symbol: str
    lookback: int | None
    position_pct: float
    slippage_bps: float
    hypothesis: str
    unsupported: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "template": self.template,
            "symbol": self.symbol,
            "lookback": self.lookback,
            "position_pct": self.position_pct,
            "slippage_bps": self.slippage_bps,
            "hypothesis": self.hypothesis,
            "unsupported": list(self.unsupported),
            "warnings": list(self.warnings),
            "source": self.source,
        }


def _detect_unsupported(text: str) -> list[str]:
    return [name for name, pattern in UNSUPPORTED_PATTERNS if re.search(pattern, text, re.I)]


def _detect_symbol(text: str) -> str:
    explicit = re.search(r"\b([A-Z]{1,5})\b", text)
    if explicit and explicit.group(1) not in {"SMA", "ETF", "US"}:
        return explicit.group(1)
    zh = re.search(r"([\u4e00-\u9fa5A-Za-z0-9\.\-]{1,10})\s*(?:的|股票|标的)", text)
    if zh and zh.group(1).isascii():
        return zh.group(1).upper()
    return "SPY"


def _detect_lookback(text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*(?:日|天|day|dma|sma)", text, re.I)
    if match:
        value = int(match.group(1))
        if 20 <= value <= 500:
            return value
    for preset in _TREND_LOOKBACKS:
        if str(preset) in text:
            return preset
    if re.search(r"趋势|trend|均线", text, re.I):
        return 200
    return None


def _detect_position(text: str) -> float:
    match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text)
    if match:
        value = float(match.group(1))
        if 1 <= value <= 100:
            return value
    return 100.0


def _detect_slippage(text: str) -> float:
    match = re.search(r"(?:滑点|slippage)[^\d]{0,6}(\d{1,3}(?:\.\d+)?)", text, re.I)
    if match:
        value = float(match.group(1))
        if 0 <= value <= 100:
            return value
    return 5.0


def draft_rules_from_intent(text: str) -> RuleDraft:
    """Deterministic intent parse — no model, no hidden capability assumptions."""
    raw = (text or "").strip()
    unsupported = _detect_unsupported(raw)
    warnings: list[str] = []
    if not raw:
        warnings.append("未提供研究想法：返回默认趋势规则草案，请补充假设。")

    equal_weight = bool(re.search(r"等权|equal[\s-]?weight|1/N|横截面", raw, re.I))
    if equal_weight:
        symbols = [s for s in DEFAULT_EQUAL_WEIGHT_UNIVERSE]
        return RuleDraft(
            template="equal_weight",
            symbol=",".join(symbols),
            lookback=None,
            position_pct=round(100.0 / len(symbols), 2),
            slippage_bps=_detect_slippage(raw),
            hypothesis=raw or "等权 1/N 基线",
            unsupported=unsupported,
            warnings=warnings,
        )

    symbol = _detect_symbol(raw)
    lookback = _detect_lookback(raw)
    if lookback is None:
        lookback = 200
        warnings.append("未识别均线周期：默认 200 日；请在规则里确认。")
    if unsupported:
        warnings.append("检测到当前工作台不支持的语义，已在草案中标出，不会被静默实现。")
    return RuleDraft(
        template="trend",
        symbol=symbol,
        lookback=lookback,
        position_pct=_detect_position(raw),
        slippage_bps=_detect_slippage(raw),
        hypothesis=raw or f"{symbol} 趋势跟随",
        unsupported=unsupported,
        warnings=warnings,
    )


def compile_trend_rules(draft: RuleDraft) -> tuple[str, dict[str, Any]]:
    """Deterministic trend-rule compilation (mirrors the web compileTrend).

    Returns (code, config); raises ValueError on out-of-range rules. Any custom
    code is never parsed — this only ever *generates* from validated rules.
    """
    if draft.template != "trend":
        raise ValueError(f"compile_trend_rules 只接受 trend 模板，收到 {draft.template}")
    symbol = (draft.symbol or "").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol):
        raise ValueError("标的代码无效（示例：SPY）")
    lookback = int(draft.lookback or 200)
    position = float(draft.position_pct)
    slippage = float(draft.slippage_bps)

    config = normalize_builder_config(
        {
            "class_name": "Spy200DmaAlgorithm",
            "hypothesis": draft.hypothesis,
            "universe": {
                "asset_class": "equity",
                "market": "US",
                "symbols": [symbol],
                "universe_filter": "single_asset",
            },
            "signal": {
                "entry_signal": f"close > SMA({lookback})",
                "exit_signal": f"close <= SMA({lookback})",
                "lookback_period": lookback,
                "rebalance_frequency": "daily",
            },
            "position_sizing": {"model": "fixed", "target_weight": position / 100.0},
            "risk": {
                "max_position_pct": position / 100.0,
                "stop_loss": None,
                "portfolio_drawdown_halt": None,
            },
            "execution": {
                "rebalance": "next_bar",
                "slippage_bps": slippage,
                "commission": "constant_1_usd",
            },
        }
    )

    code = (
        DEFAULT_STRATEGY_CODE.replace('self.AddEquity("SPY",', f'self.AddEquity("{symbol}",')
        .replace('self.SetBenchmark("SPY")', f'self.SetBenchmark("{symbol}")')
        .replace("if raw_lookback else 200", f"if raw_lookback else {lookback}")
        .replace("if raw_slippage else 5.0", f"if raw_slippage else {slippage}")
        .replace(
            "1.0 if price > sma else 0.0",
            f"{position / 100.0} if price > sma else 0.0",
        )
    )
    return code, config
