"""Fail-closed policy for user strategy source and LEAN containers."""

from __future__ import annotations

import ast
import os
from typing import Final


class StrategySandboxViolation(ValueError):
    """Raised before a strategy is written to an execution job."""

    code: Final[str] = "strategy_sandbox_violation"

    def __init__(self, message: str, *, line: int | None = None) -> None:
        location = f"第 {line} 行：" if line is not None else ""
        super().__init__(f"{self.code}: {location}{message}")
        self.line = line


_FORBIDDEN_MODULES: Final[frozenset[str]] = frozenset(
    {
        "builtins",
        "ctypes",
        "importlib",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "requests",
        "shutil",
        "socket",
        "subprocess",
        "sys",
        "urllib",
    }
)
_ALLOWED_MODULES: Final[frozenset[str]] = frozenset(
    {"AlgorithmImports", "collections", "datetime", "decimal", "math", "statistics", "typing"}
)
_FORBIDDEN_CALLS: Final[frozenset[str]] = frozenset(
    {"__import__", "compile", "eval", "exec", "input", "open"}
)
_FORBIDDEN_ATTRIBUTES: Final[frozenset[str]] = frozenset(
    {"__builtins__", "__class__", "__globals__", "__subclasses__"}
)


def _module_root(name: str | None) -> str:
    return (name or "").split(".", 1)[0]


def validate_strategy_source(source: str) -> None:
    """Reject obvious host, network, and dynamic-code escape hatches.

    This is intentionally a narrow pre-flight check, not a replacement for
    the container boundary. The container still runs with no network, a
    read-only root, a non-root user, and dropped capabilities.
    """
    try:
        tree = ast.parse(source, filename="strategy.py")
    except SyntaxError as exc:
        raise StrategySandboxViolation("策略源码语法错误", line=exc.lineno) from exc

    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _module_root(alias.name)
                if root in _FORBIDDEN_MODULES or root not in _ALLOWED_MODULES:
                    raise StrategySandboxViolation(f"禁止导入模块 {alias.name}", line=line)
        elif isinstance(node, ast.ImportFrom):
            root = _module_root(node.module)
            if root in _FORBIDDEN_MODULES or root not in _ALLOWED_MODULES:
                raise StrategySandboxViolation(f"禁止导入模块 {node.module}", line=line)
        elif isinstance(node, ast.Call):
            function = node.func.id if isinstance(node.func, ast.Name) else None
            if function in _FORBIDDEN_CALLS:
                raise StrategySandboxViolation(f"禁止调用 {function}()", line=line)
        elif isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_ATTRIBUTES:
            raise StrategySandboxViolation(f"禁止访问属性 {node.attr}", line=line)


def docker_security_args(container_user: str | None = None) -> list[str]:
    """Return the common security flags for cold and warm LEAN containers."""
    if not container_user:
        uid = getattr(os, "getuid", lambda: 65532)()
        gid = getattr(os, "getgid", lambda: 65532)()
        if uid == 0:
            uid, gid = 65532, 65532
        container_user = f"{uid}:{gid}"
    return [
        "--network",
        "none",
        "--memory",
        "2g",
        "--cpus",
        "2",
        "--pids-limit",
        "256",
        "--read-only",
        "--user",
        container_user,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--security-opt",
        "seccomp=default",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=256m",
    ]
