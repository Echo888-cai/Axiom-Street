from __future__ import annotations

from pathlib import Path

import pytest

from quant.engine.pool import LeanSlotPool


def _prebuild_shim(tmp_path: Path, image: str = "lean:test") -> Path:
    import os
    import stat

    from quant.security.sandbox import shim_dir_for_image

    target = shim_dir_for_image(image, tmp_path / "jobs")
    target.mkdir(parents=True, exist_ok=True)
    marker = target / "dotnet"
    marker.write_text("fake-dotnet", encoding="utf-8")
    marker.chmod(marker.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert os.access(marker, os.X_OK)
    return target


def test_warm_slot_command_uses_security_policy(monkeypatch, tmp_path: Path):
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(command, **_kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setattr("quant.engine.pool.subprocess.run", fake_run)
    _prebuild_shim(tmp_path)
    pool = LeanSlotPool(
        image="lean:test",
        size=1,
        jobs_root=tmp_path / "jobs",
        data_root=tmp_path / "data",
        warm=True,
    )

    pool._start_warm()

    start = calls[-1]
    assert "--read-only" in start
    assert start[start.index("--network") + 1] == "none"
    assert "/opt/axiom-dotnet:ro" in " ".join(start)


def test_unsafe_strategy_is_rejected_before_job_directory_is_created(tmp_path: Path):
    from datetime import date

    from quant.engine.base import BacktestRequest
    from quant.engine.lean import LeanQuantEngine
    from quant.security.sandbox import StrategySandboxViolation

    jobs = tmp_path / "jobs"
    request = BacktestRequest(
        backtest_id="unsafe",
        strategy_code="import os\nclass Demo: pass\n",
        strategy_class_name="Demo",
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 2),
        benchmark="SPY",
        initial_capital=100_000,
        jobs_root=jobs,
        data_root=tmp_path / "data",
    )

    with pytest.raises(StrategySandboxViolation, match="strategy_sandbox_violation"):
        LeanQuantEngine(data_root=tmp_path / "data", jobs_root=jobs).run_backtest(request)
    assert not (jobs / "unsafe").exists()


def test_cold_command_uses_explicit_dotnet_shim(tmp_path: Path):
    from quant.engine.lean import build_cold_lean_command

    shim = _prebuild_shim(tmp_path, image="lean:1")
    cmd = build_cold_lean_command(
        container_name="axiom-lean-x",
        image="lean:1",
        config_path=tmp_path / "config.json",
        algo_dir=tmp_path / "algo",
        lean_data=tmp_path / "data",
        results_dir=tmp_path / "results",
        launcher_workdir="/Lean/Launcher/bin/Debug",
        shim_dir=shim,
    )
    assert "--entrypoint" in cmd
    assert cmd[cmd.index("--entrypoint") + 1] == "/opt/axiom-dotnet/dotnet"
    assert f"{shim.resolve()}:/opt/axiom-dotnet:ro" in cmd
    dll_index = cmd.index("lean:1") + 1
    assert cmd[dll_index] == "QuantConnect.Lean.Launcher.dll"
    assert not [item for item in cmd if item.startswith("seccomp=")]
    user = cmd[cmd.index("--user") + 1]
    assert user.split(":", 1)[0] != "0"
    assert "/Lean/Launcher/bin/Debug/storage:rw,noexec,nosuid,size=64m" in " ".join(cmd)


def test_exec_command_runs_shim_as_non_root(tmp_path: Path):
    from quant.engine.lean import build_lean_exec_command

    cmd = build_lean_exec_command(
        user="501:20",
        workdir="/Lean/Launcher/bin/Debug",
        slot="axiom-lean-slot-0",
        view=tmp_path / "view",
        results_dir=tmp_path / "results",
        config_path=tmp_path / "config.json",
    )
    assert cmd[:2] == ["docker", "exec"]
    assert cmd[cmd.index("--user") + 1] == "501:20"
    dotnet_index = cmd.index("axiom-lean-slot-0") + 1
    assert cmd[dotnet_index] == "/opt/axiom-dotnet/dotnet"
    assert cmd[dotnet_index + 1] == "QuantConnect.Lean.Launcher.dll"


def test_ensure_dotnet_shim_extracts_once_then_caches(monkeypatch, tmp_path: Path):
    import stat

    from quant.security.sandbox import ensure_dotnet_shim, shim_dir_for_image

    jobs = tmp_path / "jobs"
    calls: list[list[str]] = []

    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[:2] == ["docker", "create"]:
            return Result(stdout="cid123\n")
        if command[:2] == ["docker", "cp"]:
            dest = Path(command[-1])
            dest.mkdir(parents=True, exist_ok=True)
            marker = dest / "dotnet"
            marker.write_text("dotnet", encoding="utf-8")
            marker.chmod(marker.stat().st_mode | stat.S_IXUSR)
            return Result()
        return Result()

    monkeypatch.setattr("quant.security.sandbox.subprocess.run", fake_run)
    first = ensure_dotnet_shim(image="lean:1", jobs_root=jobs, docker_env={})
    assert first == shim_dir_for_image("lean:1", jobs)
    assert (first / "dotnet").is_file()
    assert list((jobs / ".dotnet-shim").glob("*.tmp-*")) == []
    n_calls = len(calls)

    second = ensure_dotnet_shim(image="lean:1", jobs_root=jobs, docker_env={})
    assert second == first
    assert len(calls) == n_calls


def test_run_recovers_when_docker_cli_hangs_after_results_written(monkeypatch, tmp_path: Path):
    """P1-close machine-verified gap (Colima): the docker CLI can stay blocked
    in futex_wait indefinitely after the LEAN container itself exits (`--rm`
    already ran, results fully written). The engine must treat persisted,
    parseable results as completion and unblock the CLI instead of stalling
    until the hard deadline and marking a successful run FAILED."""
    import contextlib
    import shutil
    from datetime import date

    from quant.engine.base import BacktestRequest
    from quant.engine.lean import LeanQuantEngine

    fixture = Path(__file__).parent / "fixtures" / "lean_spy_200dma_2018_2020.json"
    assert fixture.is_file(), "missing result fixture"
    algo_class = "Spy200DmaAlgorithm"
    jobs = tmp_path / "jobs"

    collected: dict[str, object] = {}

    class FakeProc:
        def __init__(self, results_dir: Path):
            self.results_dir = results_dir
            self.killed = False
            self._polls = 0

        def poll(self):
            # Simulate: results appear (run finished) but the CLI never
            # observes the container die event and stays alive.
            self._polls += 1
            if self._polls == 2:
                shutil.copy(fixture, self.results_dir / f"{algo_class}.json")
            return None

        def kill(self):
            self.killed = True

        def wait(self, **_kwargs):
            return None

        def communicate(self):
            return ("docker stdout", "docker stderr")

        @property
        def returncode(self) -> int:
            return -9  # killed by us, never exited on its own

    class FakePool:
        def launcher(self):
            return None

        def lease(self, _backtest_id):
            return contextlib.nullcontext()

        def cancel(self, _backtest_id):
            pass

    def fake_popen(cmd, **_kwargs):
        results_dir: Path | None = None
        for i, part in enumerate(cmd[:-1]):
            mount = cmd[i + 1] if part == "-v" else None
            if mount and mount.endswith(":/Results"):
                results_dir = Path(mount.split(":", 1)[0])
                break
        assert results_dir is not None, f"no /Results mount in: {cmd}"
        proc = FakeProc(results_dir)
        collected["proc"] = proc
        collected["cmd"] = cmd
        return proc

    monkeypatch.setattr(
        "quant.engine.lean.ensure_lean_data", lambda *a, **k: tmp_path / "data" / "lean"
    )
    monkeypatch.setattr("quant.engine.lean.load_manifest", lambda *a, **k: {"sha256": "abc123"})
    monkeypatch.setattr("quant.engine.lean.get_pool", lambda **_k: FakePool())
    monkeypatch.setattr("quant.engine.lean.ensure_dotnet_shim", lambda **_k: tmp_path / "shim")
    monkeypatch.setattr("quant.engine.lean.subprocess.Popen", fake_popen)

    request = BacktestRequest(
        backtest_id="cli-hang",
        strategy_code="from AlgorithmImports import *\n\nclass Spy200DmaAlgorithm(QCAlgorithm):\n    def Initialize(self):\n        self.SetStartDate(2018, 1, 1)\n        self.SetEndDate(2020, 12, 31)\n        self.SetCash(100000)\n",
        strategy_class_name=algo_class,
        start_date=date(2018, 1, 1),
        end_date=date(2020, 12, 31),
        benchmark="SPY",
        initial_capital=100_000,
        jobs_root=jobs,
        data_root=tmp_path / "data",
    )

    result = LeanQuantEngine(data_root=tmp_path / "data", jobs_root=jobs).run_backtest(request)

    proc = collected["proc"]
    assert isinstance(proc, FakeProc)
    assert proc.killed, "engine must unblock the hung docker CLI after results land"
    assert result.statistics is not None
    # The CLI was unblocked after results landed, not left to the timeout.
    assert result.raw_path.endswith("Spy200DmaAlgorithm.json")
