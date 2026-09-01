from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from quant.data.lean_converter import ensure_lean_spy_data
from quant.data.manifest import load_manifest
from quant.engine.base import BacktestEngineResult, BacktestRequest, ProgressCallback, QuantEngine
from quant.engine.result_parser import find_result_json, parse_lean_result

LEAN_CONFIG_TEMPLATE = {
    "environment": "backtesting",
    "algorithm-type-name": "Spy200DmaAlgorithm",
    "algorithm-language": "Python",
    "algorithm-location": "/Lean/Algorithm.Python/strategy.py",
    "data-folder": "/Data/",
    "debugging": False,
    "log-handler": "QuantConnect.Logging.CompositeLogHandler",
    "messaging-handler": "QuantConnect.Messaging.Messaging",
    "job-queue-handler": "QuantConnect.Queues.JobQueue",
    "api-handler": "QuantConnect.Api.Api",
    "map-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskMapFileProvider",
    "factor-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskFactorFileProvider",
    "data-provider": "QuantConnect.Lean.Engine.DataFeeds.DefaultDataProvider",
    "object-store": "QuantConnect.Lean.Engine.Storage.LocalObjectStore",
    "data-aggregator": "QuantConnect.Lean.Engine.DataFeeds.AggregationManager",
    "symbol-minute-limit": 10000,
    "symbol-second-limit": 10000,
    "symbol-tick-limit": 10000,
    "parameters": {},
}


class LeanQuantEngine(QuantEngine):
    def __init__(
        self,
        *,
        lean_image: str | None = None,
        data_root: Path | None = None,
        jobs_root: Path | None = None,
    ) -> None:
        self.lean_image: str = (
            lean_image or os.getenv("AXIOM_LEAN_IMAGE") or "quantconnect/lean:16355"
        )
        self.data_root = Path(
            data_root if data_root is not None else os.getenv("AXIOM_DATA_ROOT") or "data"
        )
        self.jobs_root = Path(
            jobs_root if jobs_root is not None else os.getenv("AXIOM_JOBS_ROOT") or "jobs"
        )
        self.risk_free_rate = float(os.getenv("AXIOM_RISK_FREE_RATE") or 0.0)
        self._containers: dict[str, str] = {}

    def _docker_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if "DOCKER_HOST" not in env:
            colima_sock = Path.home() / ".colima" / "default" / "docker.sock"
            if colima_sock.exists():
                env["DOCKER_HOST"] = f"unix://{colima_sock}"
        # Prefer Homebrew docker on Apple Silicon
        brew_bin = "/opt/homebrew/bin"
        if Path(brew_bin).exists():
            env["PATH"] = f"{brew_bin}:{env.get('PATH', '')}"
        return env

    def health_check(self) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", self.lean_image],
                capture_output=True,
                text=True,
                check=False,
                env=self._docker_env(),
            )
            available = result.returncode == 0
        except FileNotFoundError:
            available = False
        return {
            "engine": "lean",
            "image": self.lean_image,
            "docker_available": available,
        }

    def cancel_backtest(self, backtest_id: str) -> None:
        name = self._containers.get(backtest_id) or f"axiom-lean-{backtest_id[:8]}"
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)

    def run_backtest(
        self,
        request: BacktestRequest,
        on_progress: ProgressCallback | None = None,
    ) -> BacktestEngineResult:
        def progress(step: str) -> None:
            if on_progress:
                on_progress(step)

        progress("Preparing environment")
        job_dir = (request.jobs_root or self.jobs_root) / request.backtest_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
        algo_dir = job_dir / "algorithm"
        results_dir = job_dir / "results"
        algo_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)

        progress("Loading data")
        data_root = request.data_root or self.data_root
        lean_data = ensure_lean_spy_data(data_root)
        manifest = load_manifest(data_root)
        data_version = manifest.get("sha256", "unknown")

        strategy_path = algo_dir / "strategy.py"
        strategy_path.write_text(request.strategy_code, encoding="utf-8")

        config = dict(LEAN_CONFIG_TEMPLATE)
        config["algorithm-type-name"] = request.strategy_class_name
        config["parameters"] = {
            **request.parameters,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "initial_capital": str(request.initial_capital),
            "benchmark": request.benchmark,
        }
        config_path = job_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        container_name = f"axiom-lean-{request.backtest_id[:8]}"
        self._containers[request.backtest_id] = container_name

        progress("Running algorithm")
        cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--memory",
            "2g",
            "--cpus",
            "2",
            "--pids-limit",
            "256",
            "--mount",
            f"type=bind,source={config_path.resolve()},target=/Lean/Launcher/config.json,readonly",
            "-v",
            f"{algo_dir.resolve()}:/Lean/Algorithm.Python:ro",
            "-v",
            f"{lean_data.resolve()}:/Data:ro",
            "-v",
            f"{results_dir.resolve()}:/Results",
            self.lean_image,
            "--data-folder",
            "/Data",
            "--results-destination-folder",
            "/Results",
            "--config",
            "/Lean/Launcher/config.json",
        ]

        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False, env=self._docker_env()
        )
        (job_dir / "docker_stdout.log").write_text(proc.stdout or "", encoding="utf-8")
        (job_dir / "docker_stderr.log").write_text(proc.stderr or "", encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(
                f"LEAN docker exited with {proc.returncode}: {(proc.stderr or proc.stdout)[-2000:]}"
            )

        progress("Calculating metrics")
        # Wait briefly for filesystem sync
        time.sleep(0.2)
        result_json = find_result_json(results_dir)
        if not result_json:
            raise RuntimeError("LEAN completed but no result JSON was found")

        parsed = parse_lean_result(result_json, risk_free_rate=self.risk_free_rate)
        progress("Generating validation report")

        return BacktestEngineResult(
            engine_version=self.lean_image,
            data_version=data_version,
            statistics=parsed["metrics"],
            equity=parsed["equity"],
            trades=parsed["trades"],
            monthly_returns=parsed["monthly_returns"],
            raw_path=str(result_json),
        )
