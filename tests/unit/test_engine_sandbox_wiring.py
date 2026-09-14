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
