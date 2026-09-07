"""Copilot provider seam tests (P5-1: noop only, no outbound calls)."""

from __future__ import annotations

import pytest

from services.api.services.copilot.providers import NoopProvider, get_provider


def test_default_provider_is_noop() -> None:
    provider = get_provider()
    assert isinstance(provider, NoopProvider)
    assert provider.name == "noop"
    assert provider.enabled is False


def test_noop_synthesize_never_returns_text() -> None:
    provider = get_provider()
    assert provider.synthesize({}) is None
    assert provider.synthesize({"total_trials": 47, "by_snapshot": []}) is None


def test_unknown_provider_fails_loud(monkeypatch) -> None:
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("STREET_COPILOT_PROVIDER", "anthropic")
    try:
        with pytest.raises(ValueError, match="anthropic"):
            get_provider()
    finally:
        get_settings.cache_clear()
