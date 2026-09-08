"""Pure portfolio attribution tests (E8-1)."""

from __future__ import annotations

import pytest

from quant.portfolio.attribution import AttributionObservation, compute_brinson_attribution


def test_brinson_effects_reconstruct_portfolio_active_return() -> None:
    result = compute_brinson_attribution(
        [
            AttributionObservation("trend", 0.6, 0.10, 0.05),
            AttributionObservation("carry", 0.4, 0.00, 0.02),
        ]
    )

    assert result.portfolio_return == pytest.approx(0.06)
    assert result.benchmark_return == pytest.approx(0.035)
    assert result.allocation_effect == pytest.approx(0.003)
    assert result.selection_effect == pytest.approx(0.015)
    assert result.interaction_effect == pytest.approx(0.007)
    assert result.active_return == pytest.approx(0.025)
    assert (
        result.allocation_effect + result.selection_effect + result.interaction_effect
        == pytest.approx(result.active_return)
    )


def test_attribution_rejects_duplicate_or_unmapped_inputs() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        compute_brinson_attribution(
            [
                AttributionObservation("trend", 0.5, 0.1, 0.05),
                AttributionObservation("trend", 0.5, 0.1, 0.05),
            ]
        )

    with pytest.raises(ValueError, match="weights"):
        compute_brinson_attribution([AttributionObservation("trend", 0.9, 0.1, 0.05)])


def test_attribution_rejects_non_finite_returns() -> None:
    with pytest.raises(ValueError, match="finite"):
        compute_brinson_attribution([AttributionObservation("trend", 1.0, float("nan"), 0.05)])
