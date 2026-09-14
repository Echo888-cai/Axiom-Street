"""Fail-closed policy for user strategy source and LEAN containers."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from pathlib import Path
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


def default_container_user(container_user: str | None = None) -> str:
    """Host-mapped non-root user for LEAN containers (owns result files)."""
    if container_user:
        return container_user
    uid = getattr(os, "getuid", lambda: 65532)()
    gid = getattr(os, "getgid", lambda: 65532)()
    if uid == 0:
        uid, gid = 65532, 65532
    return f"{uid}:{gid}"


def docker_security_args(container_user: str | None = None) -> list[str]:
    """Return the common security flags for cold and warm LEAN containers."""
    user = default_container_user(container_user)
    # NOTE: no explicit seccomp option. Docker applies its built-in default
    # profile when none is given; passing seccomp=default makes Docker treat
    # "default" as a profile *file* and the run fails (exit 125) on daemons
    # without that file (e.g. Colima/moby). Confinement stays: no network,
    # read-only rootfs, non-root, no-new-privileges, all caps dropped.
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
        user,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=256m",
    ]


DOTNET_MOUNT_POINT: Final[str] = "/opt/axiom-dotnet"
DOTNET_ENTRYPOINT: Final[str] = "/opt/axiom-dotnet/dotnet"


def storage_tmpfs_args(launcher_workdir: str | None) -> list[str]:
    """Writable scratch for LEAN's object-store directory.

    LEAN persists its object store under ``<workdir>/storage`` even for
    backtests; with a read-only rootfs that write fails. A small ephemeral
    tmpfs keeps the rest of the rootfs read-only (noexec, nosuid).
    """
    if not launcher_workdir:
        return []
    return ["--tmpfs", f"{launcher_workdir.rstrip('/')}/storage:rw,noexec,nosuid,size=64m"]


def shim_dir_for_image(image: str, jobs_root: str | Path) -> Path:
    """Host cache dir holding the dotnet runtime extracted from an image."""
    tag = re.sub(r"[^A-Za-z0-9_.-]+", "_", image)
    return Path(jobs_root) / ".dotnet-shim" / tag


def ensure_dotnet_shim(
    *,
    image: str,
    jobs_root: str | Path,
    docker_env: dict[str, str] | None = None,
    timeout_seconds: int = 600,
) -> Path:
    """Make the image's dotnet runtime mountable at a traversable path.

    The pinned LEAN image keeps dotnet under ``/root/.dotnet`` with ``/root``
    at 0700, so a non-root ``--user`` run cannot resolve it from PATH
    (proven: ``exec: "dotnet": executable file not found``). The runtime
    bytes are extracted once per image tag into ``jobs_root/.dotnet-shim``
    and bind-mounted read-only at :data:`DOTNET_MOUNT_POINT`; callers then
    use :data:`DOTNET_ENTRYPOINT` explicitly. Same bytes, same image —
    fingerprints and evidence are unaffected.
    """
    target = shim_dir_for_image(image, jobs_root)
    marker = target / "dotnet"
    if marker.is_file() and os.access(marker, os.X_OK):
        return target
    staging = target.parent / f"{target.name}.tmp-{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    env = docker_env if docker_env is not None else os.environ.copy()
    try:
        created = subprocess.run(
            ["docker", "create", image],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=120,
        )
        if created.returncode != 0 or not created.stdout.strip():
            raise RuntimeError(created.stderr.strip() or f"docker create failed for {image}")
        container_id = created.stdout.strip()
        staged_marker = staging / "dotnet"
        try:
            copied = subprocess.run(
                ["docker", "cp", f"{container_id}:/root/.dotnet/.", str(staging)],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=timeout_seconds,
            )
            if copied.returncode != 0 or not staged_marker.is_file():
                raise RuntimeError(copied.stderr.strip() or f"dotnet runtime not found in {image}")
        finally:
            subprocess.run(
                ["docker", "rm", container_id],
                capture_output=True,
                check=False,
                env=env,
                timeout=120,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"dotnet shim extraction failed for {image}: {exc}") from exc
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)
    return target
