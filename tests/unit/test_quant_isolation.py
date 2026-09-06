"""Boundary lock: ``quant/`` must never import web/service frameworks.

``quant/`` is the pure quant core. The moment a module inside it imports
FastAPI, Celery, SQLAlchemy, Redis, or any ``services.*`` module, the layering
boundary has been crossed. This test is the grep-able invariant that prevents
regression, because it runs in CI alongside the unit suite.
"""

from __future__ import annotations

import ast
from pathlib import Path

QUANT_DIR = Path(__file__).resolve().parents[2] / "quant"

# Top-level packages that must never be imported by quant code. Importing a
# `services.*` sibling (or FastAPI/Celery/ORM/web server) means quant logic has
# leaked into the wrong layer or vice versa.
FORBIDDEN_TOPS = {"fastapi", "celery", "sqlalchemy", "redis", "uvicorn", "starlette", "services"}


def _quant_modules() -> list[Path]:
    return sorted(p for p in QUANT_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _imported_tops(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tops = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            tops = [node.module.split(".")[0]]
        else:
            continue
        for top in tops:
            if top in FORBIDDEN_TOPS:
                found.append((top, node.lineno))
    return found


def test_quant_core_never_imports_web_or_service_frameworks() -> None:
    offenders: list[tuple[str, str, int]] = []
    for path in _quant_modules():
        for top, lineno in _imported_tops(path):
            offenders.append((top, str(path.relative_to(QUANT_DIR.parent)), lineno))
    assert not offenders, "quant/ 违反分层边界,禁止 import: " + repr(offenders)


def test_boundary_lock_covers_all_quant_sources() -> None:
    """The scanner must actually find .py files, or the lock is vacuous."""
    modules = _quant_modules()
    assert len(modules) > 20, f"边界扫描锁疑似失效,只发现 {len(modules)} 个 quant 模块"
