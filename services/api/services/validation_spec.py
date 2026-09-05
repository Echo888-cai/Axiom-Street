"""ValidationSpec registry — single source of truth for all 8 validation kinds.

Each validation kind is defined once here. The API layer, worker layer, and
frontend form layer all derive from this registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar

from pydantic import BaseModel, Field

from quant.validation.bootstrap import DEFAULT_CONFIDENCE, DEFAULT_N_BOOT
from quant.validation.cost import (
    DEFAULT_COSTS_BPS,
    DEFAULT_REALISTIC_BPS,
    FEE_PARAMETER,
    SLIPPAGE_PARAMETER,
)
from quant.validation.cost import MAX_GRID as COST_MAX_GRID
from quant.validation.cost import MIN_GRID as COST_MIN_GRID
from quant.validation.regime import BEAR_DRAWDOWN, MIN_AXIS_OBS, VOL_WINDOW
from quant.validation.sensitivity import DEFAULT_LOOKBACK_GRID
from quant.validation.sensitivity import MAX_GRID as SENS_MAX_GRID
from quant.validation.sensitivity import MIN_GRID as SENS_MIN_GRID
from quant.validation.walk_forward import WalkForwardSpec, build_folds
from services.api.models import ValidationKind

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from services.api.models import Backtest, StrategyVersion

T = TypeVar("T", bound=BaseModel)


class ValidationSpec(ABC, Generic[T]):
    """Abstract specification for one validation kind."""

    kind: ValidationKind
    display_name: str
    description: str
    auto_on_backtest: bool  # whether to run automatically after a backtest completes

    @abstractmethod
    def params_schema(self) -> type[T]:
        """Pydantic model for the validation parameters."""

    @abstractmethod
    def step_count(self, params: T) -> int:
        """Number of progress steps for the progress bar."""

    @abstractmethod
    def runner(self) -> Callable:
        """Function that executes the validation (worker task or auto-run)."""

    @abstractmethod
    def sync_runner(self) -> Callable:
        """Function that executes the validation synchronously (for sync mode)."""

    @abstractmethod
    def gate_check(self, run_result: dict[str, Any]) -> bool:
        """Check if the validation passed (used by VALIDATED gate)."""

    def prepare_params(
        self, db: Session, version: StrategyVersion, template: Backtest, validated_params: T
    ) -> dict[str, Any]:
        """Hook to add computed params (e.g., walk-forward folds).
        Called before creating the ValidationRun row.
        """
        return validated_params.model_dump(mode="json")

    def validate_strategy(self, db: Session, version: StrategyVersion, validated_params: T) -> None:
        """Optional pre-backtest validation of the strategy code.
        Called before _template_backtest. Raise HTTPException to fail early.
        """
        pass


# --- Walk-Forward ---


class WalkForwardParams(BaseModel):
    mode: str = Field(default="anchored", pattern="^(anchored|rolling)$")
    train_years: int = Field(default=3, ge=1)
    test_years: int = Field(default=1, ge=1)
    embargo_days: int = Field(default=1, ge=1)
    start_date: date | None = None
    end_date: date | None = None


class WalkForwardSpecImpl(ValidationSpec[WalkForwardParams]):
    kind = ValidationKind.WALK_FORWARD
    display_name = "Walk-Forward"
    description = "Rolling train/test folds across full history"
    auto_on_backtest = False

    def params_schema(self) -> type[WalkForwardParams]:
        return WalkForwardParams

    def step_count(self, params: WalkForwardParams) -> int:
        # We don't know folds until we build them, but we can estimate
        # Default to 4 folds as a reasonable minimum
        return max(4, 1)

    def runner(self) -> Callable:
        from services.worker.tasks import run_walk_forward_task

        return run_walk_forward_task

    def sync_runner(self) -> Callable:
        from services.worker.tasks import execute_walk_forward

        return execute_walk_forward

    def gate_check(self, run_result: dict[str, Any]) -> bool:
        return run_result.get("passed", False)

    def prepare_params(
        self,
        db: Session,
        version: StrategyVersion,
        template: Backtest,
        validated_params: WalkForwardParams,
    ) -> dict[str, Any]:
        start = validated_params.start_date or template.start_date
        end = validated_params.end_date or template.end_date
        mode = validated_params.mode.strip().lower()
        folds = build_folds(
            WalkForwardSpec(
                start=start,
                end=end,
                train_years=validated_params.train_years,
                test_years=validated_params.test_years,
                mode=mode,
                embargo_days=validated_params.embargo_days,
            )
        )
        params_dict = validated_params.model_dump(mode="json")
        params_dict.update(
            {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "benchmark": template.benchmark,
                "initial_capital": template.initial_capital,
                "data_snapshot_id": str(template.data_snapshot_id)
                if template.data_snapshot_id
                else None,
                "universe_snapshot": template.universe_snapshot or [],
                "parameters": template.parameters or {},
                "folds": [fold.to_dict() for fold in folds],
            }
        )
        return params_dict


# --- DSR ---


class DSRParams(BaseModel):
    # DSR is computed automatically from trial ledger, no user parameters
    pass


class DSRSpecImpl(ValidationSpec[DSRParams]):
    kind = ValidationKind.DSR
    display_name = "Deflated Sharpe Ratio"
    description = "Multiple-testing & non-normality corrected Sharpe"
    auto_on_backtest = True

    def params_schema(self) -> type[DSRParams]:
        return DSRParams

    def step_count(self, params: DSRParams) -> int:
        return 1

    def runner(self) -> Callable:
        from services.api.services.validation import record_dsr_for_backtest

        return record_dsr_for_backtest

    def sync_runner(self) -> Callable:
        from services.api.services.validation import record_dsr_for_backtest

        return record_dsr_for_backtest

    def gate_check(self, run_result: dict[str, Any]) -> bool:
        return run_result.get("passed", False)


# --- PBO ---


class PBOParams(BaseModel):
    parameter_key: str = Field(default="lookback")
    values: list[int] = Field(default_factory=list, min_length=2, max_length=12)
    start_date: date | None = None
    end_date: date | None = None


class PBOSpecImpl(ValidationSpec[PBOParams]):
    kind = ValidationKind.PBO
    display_name = "Probability of Backtest Overfitting"
    description = "CSCV over parameter grid"
    auto_on_backtest = False

    def params_schema(self) -> type[PBOParams]:
        return PBOParams

    def step_count(self, params: PBOParams) -> int:
        return max(len(params.values), 1)

    def runner(self) -> Callable:
        from services.worker.tasks import run_pbo_scan_task

        return run_pbo_scan_task

    def sync_runner(self) -> Callable:
        from services.worker.tasks import execute_pbo_scan

        return execute_pbo_scan

    def validate_strategy(
        self, db: Session, version: StrategyVersion, validated_params: PBOParams
    ) -> None:
        from fastapi import HTTPException, status

        from quant.metrics.pbo import LOOKBACK_PARAMETER, strategy_reads_lookback

        if not strategy_reads_lookback(version.code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    '该版本没有读取 LEAN 参数 lookback（GetParameter("lookback")）。'
                    "扫一个策略读不到的字段会得到相同净值，PBO 没有意义。请先提交新版本。"
                ),
            )
        if validated_params.parameter_key != LOOKBACK_PARAMETER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="目前只支持扫描 LEAN 参数 lookback，不要扫策略读不到的字段。",
            )
        values = sorted({int(v) for v in validated_params.values})
        if len(values) < 2 or len(values) > 12:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="参数扫描需要 2–12 个互异正整数。",
            )
        if any(v < 2 for v in values):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="lookback 必须 >= 2",
            )

    def gate_check(self, run_result: dict[str, Any]) -> bool:
        return run_result.get("passed", False)


# --- Sensitivity ---


class SensitivityParams(BaseModel):
    parameter_key: str = Field(default="lookback")
    values: list[int] = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None


class SensitivitySpecImpl(ValidationSpec[SensitivityParams]):
    kind = ValidationKind.SENSITIVITY
    display_name = "Parameter Sensitivity"
    description = "Sharpe surface — plateau vs knife-edge"
    auto_on_backtest = False

    def params_schema(self) -> type[SensitivityParams]:
        return SensitivityParams

    def step_count(self, params: SensitivityParams) -> int:
        return max(len(params.values), 1)

    def runner(self) -> Callable:
        from services.worker.tasks import run_sensitivity_scan_task

        return run_sensitivity_scan_task

    def sync_runner(self) -> Callable:
        from services.worker.tasks import execute_sensitivity_scan

        return execute_sensitivity_scan

    def validate_strategy(
        self, db: Session, version: StrategyVersion, validated_params: SensitivityParams
    ) -> None:
        from fastapi import HTTPException, status

        from quant.metrics.pbo import LOOKBACK_PARAMETER, strategy_reads_parameter

        if validated_params.parameter_key != LOOKBACK_PARAMETER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="目前只支持扰动 LEAN 参数 lookback，不要扫策略读不到的字段。",
            )
        if not strategy_reads_parameter(version.code, LOOKBACK_PARAMETER):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    '该版本没有读取 LEAN 参数 lookback（GetParameter("lookback")）。'
                    "扰动一个策略读不到的字段会得到相同净值，敏感性没有意义。请先提交新版本。"
                ),
            )
        values = sorted({int(v) for v in (validated_params.values or list(DEFAULT_LOOKBACK_GRID))})
        if len(values) < SENS_MIN_GRID or len(values) > SENS_MAX_GRID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"敏感性网格需要 {SENS_MIN_GRID}–{SENS_MAX_GRID} 个互异正整数。",
            )
        if any(v < 2 for v in values):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="lookback 必须 >= 2",
            )

    def gate_check(self, run_result: dict[str, Any]) -> bool:
        return run_result.get("passed", False)


# --- Cost ---


class CostParams(BaseModel):
    costs_bps: list[float] = Field(default_factory=list)
    realistic_one_way_bps: float = Field(default=DEFAULT_REALISTIC_BPS)
    slippage_parameter: str = Field(default=SLIPPAGE_PARAMETER)
    fee_parameter: str = Field(default=FEE_PARAMETER)
    start_date: date | None = None
    end_date: date | None = None


class CostSpecImpl(ValidationSpec[CostParams]):
    kind = ValidationKind.COST
    display_name = "Cost Sensitivity"
    description = "Breakeven slippage where alpha hits zero"
    auto_on_backtest = False

    def params_schema(self) -> type[CostParams]:
        return CostParams

    def step_count(self, params: CostParams) -> int:
        return max(len(params.costs_bps), 1)

    def runner(self) -> Callable:
        from services.worker.tasks import run_cost_scan_task

        return run_cost_scan_task

    def sync_runner(self) -> Callable:
        from services.worker.tasks import execute_cost_scan

        return execute_cost_scan

    def validate_strategy(
        self, db: Session, version: StrategyVersion, validated_params: CostParams
    ) -> None:
        from fastapi import HTTPException, status

        from quant.metrics.pbo import strategy_reads_parameter
        from quant.validation.cost import (
            SLIPPAGE_PARAMETER,
        )

        if not strategy_reads_parameter(version.code, SLIPPAGE_PARAMETER):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f'该版本没有读取 LEAN 参数 {SLIPPAGE_PARAMETER}（GetParameter("{SLIPPAGE_PARAMETER}")）。'
                    "成本扫描必须能改滑点，否则净值不变。请先提交新版本。"
                ),
            )
        raw_costs = (
            validated_params.costs_bps if validated_params.costs_bps else list(DEFAULT_COSTS_BPS)
        )
        costs: list[float] = []
        seen: set[float] = set()
        for item in raw_costs:
            value = float(item)
            if value != value or value < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="成本必须是 ≥ 0 的有限数，单位 bps。",
                )
            if value in seen:
                continue
            seen.add(value)
            costs.append(value)
        costs.sort()
        if len(costs) < COST_MIN_GRID or len(costs) > COST_MAX_GRID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"成本网格需要 {COST_MIN_GRID}–{COST_MAX_GRID} 个互异非负 bps。",
            )
        if 0.0 not in costs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="成本网格必须包含 0 bps，否则无法判断临界成本是否被低估。",
            )
        realistic = float(
            validated_params.realistic_one_way_bps
            if validated_params.realistic_one_way_bps is not None
            else DEFAULT_REALISTIC_BPS
        )
        if realistic != realistic or realistic < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="真实单边成本必须是 ≥ 0 的有限数。",
            )

    def gate_check(self, run_result: dict[str, Any]) -> bool:
        return run_result.get("passed", False)


# --- Bootstrap ---


class BootstrapParams(BaseModel):
    n_boot: int = Field(default=DEFAULT_N_BOOT, ge=100)
    confidence_level: float = Field(default=DEFAULT_CONFIDENCE, gt=0.5, lt=1.0)
    method: str = Field(default="stationary", pattern="^(stationary|block)$")
    mean_block_length: float | None = None
    seed: int | None = None


class BootstrapSpecImpl(ValidationSpec[BootstrapParams]):
    kind = ValidationKind.BOOTSTRAP
    display_name = "Stationary Bootstrap CI"
    description = "Sharpe/CAGR/MaxDD confidence intervals preserving autocorrelation"
    auto_on_backtest = True

    def params_schema(self) -> type[BootstrapParams]:
        return BootstrapParams

    def step_count(self, params: BootstrapParams) -> int:
        return 1

    def runner(self) -> Callable:
        from services.worker.tasks import run_bootstrap_task

        return run_bootstrap_task

    def sync_runner(self) -> Callable:
        from services.worker.tasks import execute_bootstrap

        return execute_bootstrap

    def gate_check(self, run_result: dict[str, Any]) -> bool:
        return run_result.get("passed", False)


# --- Regime ---


class RegimeParams(BaseModel):
    bear_drawdown: float = Field(default=BEAR_DRAWDOWN)
    vol_window: int = Field(default=VOL_WINDOW)
    min_axis_obs: int = Field(default=MIN_AXIS_OBS)


class RegimeSpecImpl(ValidationSpec[RegimeParams]):
    kind = ValidationKind.REGIME
    display_name = "Regime Stability"
    description = "Bull/bear, high/low vol, rate cycles — no single-regime edge"
    auto_on_backtest = True

    def params_schema(self) -> type[RegimeParams]:
        return RegimeParams

    def step_count(self, params: RegimeParams) -> int:
        return 1

    def runner(self) -> Callable:
        from services.worker.tasks import run_regime_task

        return run_regime_task

    def sync_runner(self) -> Callable:
        from services.worker.tasks import execute_regime

        return execute_regime

    def gate_check(self, run_result: dict[str, Any]) -> bool:
        return run_result.get("passed", False)


# --- SPA ---


class SPAParams(BaseModel):
    n_boot: int = Field(default=1000, ge=100)
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    seed: int | None = None


class SPASpecImpl(ValidationSpec[SPAParams]):
    kind = ValidationKind.SPA
    display_name = "Hansen SPA (Multiple Testing)"
    description = "White RC + SPA_c on trial ledger — is the best real?"
    auto_on_backtest = False

    def params_schema(self) -> type[SPAParams]:
        return SPAParams

    def step_count(self, params: SPAParams) -> int:
        return 1

    def runner(self) -> Callable:
        from services.worker.tasks import run_spa_task

        return run_spa_task

    def sync_runner(self) -> Callable:
        from services.worker.tasks import execute_spa

        return execute_spa

    def gate_check(self, run_result: dict[str, Any]) -> bool:
        return run_result.get("passed", False)


# --- Registry ---

_SPECS: dict[ValidationKind, ValidationSpec[Any]] = {
    ValidationKind.WALK_FORWARD: WalkForwardSpecImpl(),
    ValidationKind.DSR: DSRSpecImpl(),
    ValidationKind.PBO: PBOSpecImpl(),
    ValidationKind.SENSITIVITY: SensitivitySpecImpl(),
    ValidationKind.COST: CostSpecImpl(),
    ValidationKind.BOOTSTRAP: BootstrapSpecImpl(),
    ValidationKind.REGIME: RegimeSpecImpl(),
    ValidationKind.SPA: SPASpecImpl(),
}


def get_spec(kind: ValidationKind) -> ValidationSpec[Any]:
    """Get the spec for a validation kind."""
    spec = _SPECS.get(kind)
    if spec is None:
        raise KeyError(f"Unknown validation kind: {kind}")
    return spec


def all_specs() -> list[ValidationSpec[Any]]:
    """All specs in a fixed order."""
    return [
        _SPECS[ValidationKind.WALK_FORWARD],
        _SPECS[ValidationKind.DSR],
        _SPECS[ValidationKind.PBO],
        _SPECS[ValidationKind.SENSITIVITY],
        _SPECS[ValidationKind.COST],
        _SPECS[ValidationKind.BOOTSTRAP],
        _SPECS[ValidationKind.REGIME],
        _SPECS[ValidationKind.SPA],
    ]


def validated_kinds() -> list[ValidationKind]:
    """Kinds that must pass for VALIDATED status."""
    return [
        ValidationKind.WALK_FORWARD,
        ValidationKind.DSR,
        ValidationKind.PBO,
        ValidationKind.SENSITIVITY,
        ValidationKind.COST,
        ValidationKind.BOOTSTRAP,
        ValidationKind.REGIME,
        ValidationKind.SPA,
    ]


def engine_kinds() -> list[ValidationKind]:
    """Kinds that require LEAN engine runs."""
    return [
        ValidationKind.WALK_FORWARD,
        ValidationKind.PBO,
        ValidationKind.SENSITIVITY,
        ValidationKind.COST,
    ]


def auto_on_backtest_kinds() -> list[ValidationKind]:
    """Kinds that run automatically after a backtest completes."""
    return [
        ValidationKind.DSR,
        ValidationKind.BOOTSTRAP,
        ValidationKind.REGIME,
    ]


def params_schema_for(kind: ValidationKind) -> type[BaseModel]:
    """Get the Pydantic params schema for a kind."""
    return get_spec(kind).params_schema()


def step_count_for(kind: ValidationKind, params: BaseModel) -> int:
    """Get the progress step count for a kind with given params."""
    return get_spec(kind).step_count(params)


def runner_for(kind: ValidationKind) -> Callable:
    """Get the runner function for a kind."""
    return get_spec(kind).runner()


def gate_check_for(kind: ValidationKind, run_result: dict[str, Any]) -> bool:
    """Check if a validation run result passes the gate."""
    return get_spec(kind).gate_check(run_result)
