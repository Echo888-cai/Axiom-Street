from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from io import BytesIO
from uuid import UUID

from sqlalchemy.orm import Session

from services.api.models import Backtest, BacktestEquity, BacktestMetrics, Strategy, StrategyVersion
from services.api.services import backtests as backtest_service


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:+.2f}%"


def _num(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _usd(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:,.0f}"


def _pdf_latin1(text: str) -> str:
    """Helvetica cannot encode CJK. Replace, don't crash, don't invent numbers."""
    return text.encode("latin-1", "replace").decode("latin-1")


def _load(db: Session, backtest_id: UUID) -> tuple[Backtest, BacktestMetrics, list[BacktestEquity], str]:
    backtest = backtest_service.get_backtest(db, backtest_id)
    if backtest.status.value != "COMPLETED":
        raise ValueError("回测尚未完成，无法导出 tearsheet")
    metrics = backtest_service.get_metrics(db, backtest_id)
    equity, _ = backtest_service.get_equity(db, backtest_id, limit=50_000, offset=0)
    version = db.get(StrategyVersion, backtest.strategy_version_id)
    strategy = db.get(Strategy, version.strategy_id) if version else None
    name = strategy.name if strategy else str(backtest.id)
    return backtest, metrics, equity, name


def render_html(db: Session, backtest_id: UUID) -> str:
    backtest, metrics, equity, name = _load(db, backtest_id)
    extras = metrics.extras or {}
    rows = [
        ("总收益", _pct(metrics.total_return)),
        ("CAGR", _pct(metrics.cagr)),
        ("夏普", _num(metrics.sharpe)),
        ("Deflated Sharpe", _num(metrics.deflated_sharpe)),
        ("Probabilistic Sharpe", _num(metrics.probabilistic_sharpe)),
        ("试验次数 N", str(metrics.dsr_n_trials) if metrics.dsr_n_trials is not None else "—"),
        ("最大回撤", _pct(metrics.max_drawdown)),
        ("波动率", _pct(metrics.volatility)),
        ("超额收益", _pct(metrics.excess_return)),
        ("CAPM α", _pct(metrics.alpha_capm)),
        ("β", _num(metrics.beta)),
        ("信息比率", _num(metrics.information_ratio)),
        ("索提诺", _num(metrics.sortino)),
        ("卡尔玛", _num(metrics.calmar)),
        ("VaR 95%", _pct(metrics.var_95)),
        ("CVaR 95%", _pct(metrics.cvar_95)),
        ("尾部比", _num(metrics.tail_ratio)),
        ("毛暴露", _num(metrics.gross_exposure)),
        ("净暴露", _num(metrics.net_exposure)),
        ("换手", _num(metrics.turnover)),
        ("成交笔数", _num(metrics.trade_count, 0)),
        ("手续费", _usd(metrics.commission)),
        ("期末权益", _usd(metrics.final_equity)),
    ]
    cells = "".join(
        f"<tr><th>{escape(label)}</th><td class='tabular'>{escape(value)}</td></tr>"
        for label, value in rows
    )
    eq_n = len(equity)
    first = equity[0].strategy_value if equity else None
    last = equity[-1].strategy_value if equity else None
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Tearsheet · {escape(name)}</title>
  <style>
    body {{ font-family: Inter, -apple-system, sans-serif; color: #111; background: #fff; margin: 32px; }}
    h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 8px; }}
    .meta {{ color: #667085; font-size: 12px; margin-bottom: 24px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 640px; }}
    th, td {{ border-bottom: 1px solid #EAECF0; padding: 8px 0; font-size: 13px; text-align: left; }}
    th {{ color: #667085; font-weight: 500; width: 40%; }}
    .tabular {{ font-variant-numeric: tabular-nums; }}
    .note {{ margin-top: 24px; font-size: 11px; color: #667085; max-width: 640px; }}
    @media print {{ body {{ margin: 16px; }} }}
  </style>
</head>
<body>
  <h1>{escape(name)}</h1>
  <div class="meta">
    {escape(str(backtest.start_date))} → {escape(str(backtest.end_date))}
    · 本金 {_usd(backtest.initial_capital)}
    · 基准 {escape(backtest.benchmark)}
    · 快照 {escape((backtest.data_version or "—")[:16])}
    · 引擎 {escape(backtest.engine_version or "—")}
    · 权益点 {eq_n}（{_usd(first)} → {_usd(last)}）
  </div>
  <table>{cells}</table>
  <p class="note">
    指标由 Axiom 从权益序列计算，LEAN 原始统计仅作对账（extras）。
    本页不含伪造曲线。Deflated Sharpe 已计入试验台账 N={escape(str(metrics.dsr_n_trials or "—"))}。
    导出时间 {escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))}。
    rebase={escape(str(bool(extras.get("benchmark_rebased"))))}.
  </p>
</body>
</html>
"""


def render_pdf(db: Session, backtest_id: UUID) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    backtest, metrics, equity, name = _load(db, backtest_id)
    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 20 * mm
    page.setFont("Helvetica-Bold", 14)
    page.drawString(18 * mm, y, _pdf_latin1(f"Axiom Street  {name[:64]}"))
    y -= 8 * mm
    page.setFont("Helvetica", 9)
    page.setFillColorRGB(0.4, 0.44, 0.51)
    page.drawString(
        18 * mm,
        y,
        _pdf_latin1(
            f"{backtest.start_date} -> {backtest.end_date}  capital={backtest.initial_capital:.0f}  "
            f"benchmark={backtest.benchmark}"
        ),
    )
    y -= 5 * mm
    page.drawString(
        18 * mm,
        y,
        _pdf_latin1(
            f"snapshot={(backtest.data_version or '-')[:20]}  engine={backtest.engine_version or '-'}"
        ),
    )
    page.setFillColorRGB(0, 0, 0)
    y -= 12 * mm

    rows: list[tuple[str, str]] = [
        ("Deflated Sharpe", _num(metrics.deflated_sharpe)),
        ("Probabilistic Sharpe", _num(metrics.probabilistic_sharpe)),
        ("Trials N", str(metrics.dsr_n_trials) if metrics.dsr_n_trials is not None else "-"),
        ("Sharpe", _num(metrics.sharpe)),
        ("CAGR", _pct(metrics.cagr)),
        ("Total return", _pct(metrics.total_return)),
        ("Max drawdown", _pct(metrics.max_drawdown)),
        ("Volatility", _pct(metrics.volatility)),
        ("Excess return", _pct(metrics.excess_return)),
        ("CAPM alpha", _pct(metrics.alpha_capm)),
        ("Beta", _num(metrics.beta)),
        ("Information ratio", _num(metrics.information_ratio)),
        ("Gross exposure", _num(metrics.gross_exposure)),
        ("Net exposure", _num(metrics.net_exposure)),
        ("Turnover", _num(metrics.turnover)),
        ("Trades", _num(metrics.trade_count, 0)),
        ("Commission", _usd(metrics.commission)),
        ("Final equity", _usd(metrics.final_equity)),
    ]
    page.setFont("Helvetica", 10)
    for label, value in rows:
        page.drawString(18 * mm, y, label)
        page.drawRightString(width - 18 * mm, y, value.replace("—", "-"))
        y -= 6 * mm
        if y < 70 * mm:
            break

    values = [p.strategy_value for p in equity if p.strategy_value is not None]
    if len(values) >= 2:
        y -= 4 * mm
        page.setFont("Helvetica", 9)
        page.setFillColorRGB(0.4, 0.44, 0.51)
        page.drawString(18 * mm, y, "Equity (Axiom series)")
        page.setFillColorRGB(0.09, 0.47, 1.0)
        chart_top = y - 6 * mm
        chart_bottom = 22 * mm
        chart_left = 18 * mm
        chart_right = width - 18 * mm
        lo, hi = min(values), max(values)
        span = hi - lo if hi != lo else 1.0
        n = len(values)
        path = page.beginPath()
        for i, equity_value in enumerate(values):
            x = chart_left + (chart_right - chart_left) * (i / (n - 1))
            py = chart_bottom + (chart_top - chart_bottom) * ((equity_value - lo) / span)
            if i == 0:
                path.moveTo(x, py)
            else:
                path.lineTo(x, py)
        page.setStrokeColorRGB(0.09, 0.47, 1.0)
        page.setLineWidth(1.2)
        page.drawPath(path, stroke=1, fill=0)

    page.setFillColorRGB(0.4, 0.44, 0.51)
    page.setFont("Helvetica", 8)
    page.drawString(
        18 * mm,
        12 * mm,
        "Metrics computed by Axiom from the return series. LEAN statistics are extras only. No mock P&L.",
    )
    page.showPage()
    page.save()
    return buf.getvalue()
