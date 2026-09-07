"""Boundary locks for the copilot (P5-1 + P5-2 worker ledger refinement).

Phase 5 hard constraints 1 & 2, enforced at the code level: copilot sources
may not import write-path services (anything that can touch risk settings,
validation status or the VALIDATED write point), may not call ORM write APIs,
and may not so much as reference the columns that carry research IP or raw
market data — strategy source (``code``/``config``), parameter JSON and price
series stay out of the copilot's read surface so no provider adapter
(aggregate-only outbound, P5-2) can ever receive them.

P5-2 refinement: the worker synthesize task (``worker/tasks/copilot.py``) is
also scanned — same import and column locks — and may perform ORM writes ONLY
inside its single ledger-write helper ``_record_insight`` (the copilot's own
``copilot_insights`` table). Any other write call site fails the lock.

Add any future copilot source to ``_api_sources`` / ``_all_sources``.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COPILOT_DIR = ROOT / "services" / "api" / "services" / "copilot"
ROUTER_FILE = ROOT / "services" / "api" / "routers" / "copilot.py"
TASK_FILE = ROOT / "services" / "worker" / "tasks" / "copilot.py"

# The worker task orchestrates the outbound call and owns the ledger write, so
# it must not sit outside every lock; but ORM writes are permitted in exactly
# one helper there (see _record_insight_name).
LEDGER_WRITE_HELPER = "_record_insight"

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


def _api_sources() -> list[Path]:
    files = sorted(p for p in COPILOT_DIR.rglob("*.py") if "__pycache__" not in p.parts)
    if ROUTER_FILE.exists():
        files.append(ROUTER_FILE)
    return files


def _all_sources() -> list[Path]:
    sources = _api_sources()
    if TASK_FILE.exists():
        sources.append(TASK_FILE)
    return sources


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


def _write_calls_outside_helper(path: Path) -> list[tuple[str, int, str]]:
    """ORM write calls outside the ledger helper (worker task only)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    allowed: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != LEDGER_WRITE_HELPER:
            continue
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr in FORBIDDEN_CALLS
            ):
                allowed.add((call.lineno, call.col_offset))
    outside: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in FORBIDDEN_CALLS and (node.lineno, node.col_offset) not in allowed:
            outside.append((node.func.attr, node.lineno, LEDGER_WRITE_HELPER))
    return outside


def _referenced_columns(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_COLUMN_ATTRS:
            found.append((node.attr, node.lineno))
    return found


def test_copilot_never_imports_write_paths() -> None:
    offenders: list[tuple[str, str, int]] = []
    for path in _all_sources():
        for banned, lineno in _imported_forbidden(path):
            offenders.append((banned, str(path.relative_to(ROOT)), lineno))
    assert not offenders, "copilot 违反约束一/二,禁止 import 写面模块: " + repr(offenders)


def test_api_copilot_never_calls_orm_write_api() -> None:
    offenders: list[tuple[str, str, int]] = []
    for path in _api_sources():
        for call, lineno in _called_forbidden(path):
            offenders.append((call, str(path.relative_to(ROOT)), lineno))
    assert not offenders, "copilot 调用 ORM 写 API,违反只读边界: " + repr(offenders)


def test_worker_task_writes_only_its_own_ledger_helper() -> None:
    """P5-2: the synthesize task may write, but only in the ledger helper."""
    offenders = _write_calls_outside_helper(TASK_FILE)
    assert not offenders, (
        f"{TASK_FILE.relative_to(ROOT)} 存在 ledger 写点以外的 ORM 写调用: " + repr(offenders)
    )


def test_copilot_never_reads_research_ip_or_market_columns() -> None:
    """Aggregate-only outbound boundary prepared at the column level."""
    offenders: list[tuple[str, str, int]] = []
    for path in _all_sources():
        for column, lineno in _referenced_columns(path):
            offenders.append((column, str(path.relative_to(ROOT)), lineno))
    assert not offenders, "copilot 触碰研究 IP/行情列(出站边界): " + repr(offenders)


def test_boundary_lock_covers_real_sources() -> None:
    """The scanner must find the actual files, or the locks are vacuous."""
    api_names = {p.name for p in _api_sources()}
    assert {
        "context.py",
        "providers.py",
        "insights.py",
        "prompts.py",
        "__init__.py",
        "copilot.py",
    } <= api_names, f"边界扫描疑似失效,来源文件缺失: {sorted(api_names)}"
    assert TASK_FILE.exists(), f"worker synthesize 任务缺失: {TASK_FILE}"
    task_tree = ast.parse(TASK_FILE.read_text(encoding="utf-8"))
    assert any(
        isinstance(n, ast.FunctionDef) and n.name == LEDGER_WRITE_HELPER
        for n in ast.walk(task_tree)
    ), "worker 任务缺失 ledger 写辅助函数,锁形同虚设"
    assert FORBIDDEN_MODULES and FORBIDDEN_CALLS and FORBIDDEN_COLUMN_ATTRS
