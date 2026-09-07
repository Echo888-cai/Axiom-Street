"""Boundary locks for the copilot (P5-1).

Phase 5 hard constraints 1 & 2, enforced at the code level: copilot sources
may not import write-path services (anything that can touch risk settings,
validation status or the VALIDATED write point), may not call ORM write APIs,
and may not so much as reference the columns that carry research IP or raw
market data — strategy source (``code``/``config``), parameter JSON and price
series stay out of the copilot's read surface so no future LLM adapter
(aggregate-only outbound, P5-2) can ever receive them.

Add any future copilot source (e.g. a P5-2 worker task) to ``_copilot_sources``.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COPILOT_DIR = ROOT / "services" / "api" / "services" / "copilot"
ROUTER_FILE = ROOT / "services" / "api" / "routers" / "copilot.py"

# Importing any of these puts a write path inside copilot code.
FORBIDDEN_MODULES: tuple[str, ...] = (
    "services.api.services.backtests",
    "services.api.services.snapshots",
    "services.api.services.strategies",
    "services.api.services.validation",
    "services.api.services.validation_spec",
    "services.api.status_machine",
)

# Session/ORM write surface: calling any attribute with these names is a write.
# (`execute` is deliberately absent — read-only SELECTs go through it; the
# dangerous forms are the session state mutations below.)
FORBIDDEN_CALLS: frozenset[str] = frozenset(
    {"add", "commit", "flush", "delete", "merge", "update", "insert"}
)

# Outbound boundary columns. Context assembly must never read or select them.
FORBIDDEN_COLUMN_ATTRS: frozenset[str] = frozenset(
    {
        "code",
        "config",
        "parameters",
        "close",
        "price",
        "open",
        "high",
        "low",
        "volume",
        "adj_close",
        "adj_open",
        "adj_high",
        "adj_low",
    }
)


def _copilot_sources() -> list[Path]:
    files = sorted(p for p in COPILOT_DIR.rglob("*.py") if "__pycache__" not in p.parts)
    if ROUTER_FILE.exists():
        files.append(ROUTER_FILE)
    return files


def _imported_forbidden(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            for banned in FORBIDDEN_MODULES:
                if name == banned or name.startswith(banned + "."):
                    found.append((banned, node.lineno))
    return found


def _called_forbidden(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in FORBIDDEN_CALLS:
            found.append((node.func.attr, node.lineno))
    return found


def _referenced_columns(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_COLUMN_ATTRS:
            found.append((node.attr, node.lineno))
    return found


def test_copilot_never_imports_write_paths() -> None:
    offenders: list[tuple[str, str, int]] = []
    for path in _copilot_sources():
        for banned, lineno in _imported_forbidden(path):
            offenders.append((banned, str(path.relative_to(ROOT)), lineno))
    assert not offenders, "copilot 违反约束一/二,禁止 import 写面模块: " + repr(offenders)


def test_copilot_never_calls_orm_write_api() -> None:
    offenders: list[tuple[str, str, int]] = []
    for path in _copilot_sources():
        for call, lineno in _called_forbidden(path):
            offenders.append((call, str(path.relative_to(ROOT)), lineno))
    assert not offenders, "copilot 调用 ORM 写 API,违反只读边界: " + repr(offenders)


def test_copilot_context_never_reads_research_ip_or_market_columns() -> None:
    """Aggregate-only outbound boundary prepared at the column level."""
    offenders: list[tuple[str, str, int]] = []
    for path in sorted(COPILOT_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for column, lineno in _referenced_columns(path):
            offenders.append((column, str(path.relative_to(ROOT)), lineno))
    assert not offenders, "copilot 触碰研究 IP/行情列(出站边界): " + repr(offenders)


def test_boundary_lock_covers_real_sources() -> None:
    """The scanner must find the actual files, or the locks are vacuous."""
    sources = _copilot_sources()
    names = {p.name for p in sources}
    assert {"context.py", "providers.py", "__init__.py", "copilot.py"} <= names, (
        f"边界扫描疑似失效,来源文件缺失: {sorted(names)}"
    )
    assert len(sources) >= 4, f"只发现 {len(sources)} 个 copilot 来源"
    assert FORBIDDEN_MODULES and FORBIDDEN_CALLS and FORBIDDEN_COLUMN_ATTRS
