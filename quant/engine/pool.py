from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def build_lean_view(job_dir: Path, lean_data: Path, map_overlay: Path | None = None) -> Path:
    """Job-local LEAN data tree that can be executed from a warm container.

    Snapshot files are symlinked (never copied, never mutated). PIT map files
    overlay ``equity/usa/map_files`` without writing into the snapshot.
    """
    view = job_dir / "lean_view"
    if view.exists():
        shutil.rmtree(view)
    view.mkdir(parents=True)

    def link(src: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(src.resolve())

    if not lean_data.exists():
        raise FileNotFoundError(f"LEAN data folder missing: {lean_data}")

    equity = lean_data / "equity"
    for child in lean_data.iterdir():
        if child.name == "equity" and (child / "usa").is_dir():
            for sub in (child / "usa").iterdir():
                if sub.name == "map_files" and map_overlay is not None:
                    continue
                link(sub, view / "equity" / "usa" / sub.name)
            continue
        link(child, view / child.name)

    if map_overlay is not None:
        link(map_overlay, view / "equity" / "usa" / "map_files")
    elif (equity / "usa" / "map_files").exists():
        link(equity / "usa" / "map_files", view / "equity" / "usa" / "map_files")
    return view


def inspect_launcher(image: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{json .Config}}"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"docker inspect failed for {image}")
    config = json.loads(result.stdout)
    entrypoint = config.get("Entrypoint") or []
    cmd = config.get("Cmd") or []
    workdir = config.get("WorkingDir") or "/Lean/Launcher/bin/Release"
    if not entrypoint:
        raise RuntimeError(f"LEAN image {image} has no Entrypoint")
    return {
        "entrypoint": list(entrypoint),
        "cmd": list(cmd),
        "workdir": str(workdir),
    }


class LeanSlotPool:
    """Resident LEAN slots: pre-pulled image + bounded concurrency + optional warm containers.

    Warm containers override the image entrypoint with ``sleep`` so a later
    ``docker exec`` can launch the original LEAN process against host-path
    job directories. If warm start fails, callers fall back to ``docker run``.
    """

    def __init__(
        self,
        *,
        image: str,
        size: int,
        jobs_root: Path,
        data_root: Path,
        docker_env: dict[str, str] | None = None,
        warm: bool | None = None,
    ) -> None:
        if size < 1:
            raise ValueError("LEAN pool size must be >= 1")
        self.image = image
        self.size = size
        self.jobs_root = Path(jobs_root)
        self.data_root = Path(data_root)
        self._env = docker_env or os.environ.copy()
        self._sema = threading.BoundedSemaphore(size)
        self._cond = threading.Condition()
        self._idle: list[str] = []
        self._busy: dict[str, str] = {}
        self._launcher: dict[str, Any] | None = None
        self._want_warm = (
            warm
            if warm is not None
            else os.getenv("STREET_LEAN_POOL_WARM", "").lower() in {"1", "true", "yes"}
        )
        self._warm = False
        self._ensure_lock = threading.Lock()
        self._ensured = False

    def ensure(self) -> None:
        with self._ensure_lock:
            if self._ensured:
                return
            self._pull_image()
            try:
                self._launcher = inspect_launcher(self.image, self._env)
            except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
                self._launcher = None
            if self._want_warm:
                try:
                    self._start_warm()
                    self._warm = True
                except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
                    self._warm = False
            self._ensured = True

    def _pull_image(self) -> None:
        inspect = subprocess.run(
            ["docker", "image", "inspect", self.image],
            capture_output=True,
            text=True,
            check=False,
            env=self._env,
            timeout=30,
        )
        if inspect.returncode == 0:
            return
        pull = subprocess.run(
            ["docker", "pull", self.image],
            capture_output=True,
            text=True,
            check=False,
            env=self._env,
            timeout=600,
        )
        if pull.returncode != 0:
            raise RuntimeError(pull.stderr.strip() or f"docker pull failed for {self.image}")

    def _start_warm(self) -> None:
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.data_root.mkdir(parents=True, exist_ok=True)
        started: list[str] = []
        for index in range(self.size):
            name = f"axiom-lean-slot-{index}"
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False, env=self._env)
            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--network",
                "none",
                "--memory",
                "2g",
                "--cpus",
                "2",
                "--pids-limit",
                "256",
                "--entrypoint",
                "sleep",
                "-v",
                f"{self.jobs_root.resolve()}:{self.jobs_root.resolve()}",
                "-v",
                f"{self.data_root.resolve()}:{self.data_root.resolve()}:ro",
                self.image,
                "86400",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=self._env, timeout=60)
            if result.returncode != 0:
                for created in started:
                    subprocess.run(
                        ["docker", "rm", "-f", created],
                        capture_output=True,
                        check=False,
                        env=self._env,
                    )
                raise RuntimeError(result.stderr.strip() or f"failed to start warm slot {name}")
            started.append(name)
        with self._cond:
            self._idle = started
            self._busy.clear()

    def launcher(self) -> dict[str, Any] | None:
        return self._launcher

    def health(self) -> dict[str, Any]:
        with self._cond:
            idle = len(self._idle)
            busy = len(self._busy)
        return {
            "image": self.image,
            "size": self.size,
            "warm": self._warm,
            "idle": idle,
            "busy": busy,
            "ensured": self._ensured,
        }

    @contextmanager
    def lease(self, backtest_id: str) -> Iterator[str | None]:
        """Yield a warm container name, or None for a cold ``docker run``.

        The semaphore is the real concurrency cap either way.
        """
        self.ensure()
        self._sema.acquire()
        container: str | None = None
        try:
            if self._warm:
                with self._cond:
                    while not self._idle:
                        self._cond.wait(timeout=1.0)
                        if not self._warm:
                            break
                    if self._idle:
                        container = self._idle.pop()
                        self._busy[container] = backtest_id
            yield container
        finally:
            if container is not None:
                with self._cond:
                    self._busy.pop(container, None)
                    self._idle.append(container)
                    self._cond.notify()
            self._sema.release()

    def cancel(self, backtest_id: str) -> None:
        with self._cond:
            names = [name for name, owner in self._busy.items() if owner == backtest_id]
        for name in names:
            subprocess.run(
                ["docker", "exec", name, "pkill", "-f", "QuantConnect.Lean"],
                capture_output=True,
                check=False,
                env=self._env,
                timeout=15,
            )


_POOLS: dict[tuple[str, int, str, str], LeanSlotPool] = {}
_POOLS_LOCK = threading.Lock()


def get_pool(
    *,
    image: str,
    size: int,
    jobs_root: Path,
    data_root: Path,
    docker_env: dict[str, str] | None = None,
    warm: bool | None = None,
) -> LeanSlotPool:
    key = (image, size, str(Path(jobs_root).resolve()), str(Path(data_root).resolve()))
    with _POOLS_LOCK:
        pool = _POOLS.get(key)
        if pool is None:
            pool = LeanSlotPool(
                image=image,
                size=size,
                jobs_root=jobs_root,
                data_root=data_root,
                docker_env=docker_env,
                warm=warm,
            )
            _POOLS[key] = pool
        return pool
