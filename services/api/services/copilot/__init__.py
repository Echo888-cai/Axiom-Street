"""AI copilot services (P5-1: read-only context + provider seam).

Structural rule: nothing in this package may import write-path services
(validation / backtests / strategies / validation_spec / status_machine) or
call ORM write APIs — enforced by ``tests/unit/test_copilot_isolation.py``.
"""

from services.api.services.copilot.context import build_context
from services.api.services.copilot.providers import get_provider

__all__ = ["build_context", "get_provider"]
