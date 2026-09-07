"""Isolation lock for the risk engine (Phase 6 WP-1).

``quant/risk`` sources are rendered verbatim into the LEAN container, so they
may import only the Python stdlib plus two sibling rendered modules
(``risk_engine`` / ``risk_gate``) and their own ``quant`` package — never
numpy-less web/service/framework tops. Anything else would break the container
build and is a layering violation.
"""

from __future__ import annotations

import ast
from pathlib import Path

RISK_DIR = Path(__file__).resolve().parents[2] / "quant" / "risk"

# Own rendered modules are importable inside the container; everything else
# must come from the stdlib.
_SELF_TOPS = {"quant", "risk_engine", "risk_gate"}
# The risk package only imports these stdlib modules (py3.9-safe allow-list;
# sys.stdlib_module_names is 3.10+).
_STDLIB_TOPS = frozenset(
    {"__future__", "dataclasses", "json", "math", "os", "pathlib", "sys", "typing"}
)
_ALLOWED_TOPS = _SELF_TOPS | _STDLIB_TOPS


def _risk_modules() -> list[Path]:
    return sorted(p for p in RISK_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _non_stdlib_tops(path: Path) -> list[tuple[str, int]]:
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
            if top not in _ALLOWED_TOPS:
                found.append((top, node.lineno))
    return found


def test_risk_sources_are_container_safe() -> None:
    offenders: list[tuple[str, str, int]] = []
    for path in _risk_modules():
        for top, lineno in _non_stdlib_tops(path):
            offenders.append((top, str(path.relative_to(RISK_DIR.parent)), lineno))
    assert not offenders, "quant/risk 必须仅用 stdlib(+自身渲染模块): " + repr(offenders)


def test_risk_lock_covers_real_sources() -> None:
    """The scanner must find the modules, or the lock is vacuous."""
    names = {p.name for p in _risk_modules()}
    assert {
        "__init__.py",
        "engine.py",
        "limits.py",
        "types.py",
        "runtime_gate.py",
        "gate.py",
    } <= names, f"quant/risk 文件缺失,锁形同虚设: {sorted(names)}"
