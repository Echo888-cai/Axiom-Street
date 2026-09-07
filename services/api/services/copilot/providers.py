"""AI provider seam for the copilot (P5-1: noop only).

P5-2 wires Anthropic here (worker-side synthesize with timeouts). Until then
the default noop provider keeps the platform fully local: no key, no outbound
call, ``synthesize()`` never returns text. What a future provider may receive
is bounded upstream in ``copilot/context.py`` — aggregate statistics only, no
strategy source, parameter JSON, or price series.
"""

from __future__ import annotations

from typing import Any, Protocol

from services.api.settings import get_settings


class Provider(Protocol):
    name: str
    enabled: bool

    def synthesize(self, context: dict[str, Any]) -> str | None:
        """Produce a narrative insight, or None when the provider is disabled."""
        ...


class NoopProvider:
    """Deterministic fallback: the platform never dials out."""

    name = "noop"
    enabled = False

    def synthesize(self, context: dict[str, Any]) -> str | None:
        return None


_REGISTRY: dict[str, type[Provider]] = {"noop": NoopProvider}


def get_provider() -> Provider:
    """Resolve the configured provider. Unknown names fail loud (misconfig)."""
    name = get_settings().copilot_provider
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ValueError(f"copilot provider 未注册: {name!r}(P5-1 仅实现 noop)") from None
