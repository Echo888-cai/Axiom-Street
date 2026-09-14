"""P4.2 change review: what a rule/code change does before it can become a version.

The review is read-only. It never writes a version, never sends source code
outbound (outbound_scope states what the Copilot may see), and it surfaces:

- a line diff between the current code and the proposed code;
- syntax check (the same language check the editor uses);
- dependency scan (imports beyond ``AlgorithmImports`` are flagged);
- future-data scan (obvious look-ahead patterns);
- version conflict (reusing the P2.1 stale-draft rule).
"""

from __future__ import annotations

import ast
import difflib
import re
from typing import Any

_ALLOWED_IMPORT = "AlgorithmImports"

# 明显的前视/未来数据模式：命中即需要人工复核。
_FUTURE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"History\([^)]*,\s*0\s*\)", "History(..., 0) 读取当前未完成 bar"),
    (r"\.GetLastData\(\)", "GetLastData 可能在收盘前读到未完成数据"),
    (r"set_start_date\s*\(\s*202[6-9]", "起始日期落在未来/未来数据窗口"),
)


def _syntax_issues(code: str) -> list[str]:
    try:
        ast.parse(code or "")
    except SyntaxError as exc:
        return [f"语法错误：第 {exc.lineno} 行 {exc.msg}"]
    return []


def _dependency_issues(code: str) -> list[str]:
    issues: list[str] = []
    for line in (code or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            module = stripped.split()[1]
            if module != _ALLOWED_IMPORT:
                issues.append(f"引入白名单外的依赖：{stripped}")
    return issues


def _future_data_issues(code: str) -> list[str]:
    issues: list[str] = []
    for pattern, message in _FUTURE_PATTERNS:
        if re.search(pattern, code or "", re.I):
            issues.append(message)
    return issues


def diff_summary(before: str, after: str) -> dict[str, Any]:
    diff = list(
        difflib.unified_diff(
            (before or "").splitlines(), (after or "").splitlines(), lineterm="", n=0
        )
    )
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    return {"added": added, "removed": removed, "lines": diff[:400]}


def review_rule_change(
    *,
    current_code: str,
    proposed_code: str,
    unsupported: list[str] | None = None,
    source_version_id: str | None = None,
    latest_version_id: str | None = None,
) -> dict[str, Any]:
    """Read-only review report. ``outbound_scope`` documents exactly what could
    leave the machine for this change: nothing here — reviews are local."""
    syntax = _syntax_issues(proposed_code)
    dependencies = _dependency_issues(proposed_code)
    future = _future_data_issues(proposed_code)
    conflict = bool(
        source_version_id and latest_version_id and source_version_id != latest_version_id
    )
    blocking = [
        *syntax,
        *dependencies,
        *future,
        *(["草稿基于旧版本：保存会被拒绝（draft_stale）"] if conflict else []),
    ]
    return {
        "diff": diff_summary(current_code, proposed_code),
        "checks": {
            "syntax": {"ok": not syntax, "issues": syntax},
            "dependencies": {"ok": not dependencies, "issues": dependencies},
            "future_data": {"ok": not future, "issues": future},
            "version_conflict": {"stale": conflict},
        },
        "unsupported": list(unsupported or []),
        "blocking": blocking,
        "approvable": not blocking,
        "writes_version": False,
        "outbound_scope": {
            "sends_source_code": False,
            "sends": ["聚合事实（收益/回撤/闸门状态）"],
            "note": "审查在本地完成；Copilot 仍然只发送聚合事实，不发送源码、配置或原始行情。",
        },
    }
