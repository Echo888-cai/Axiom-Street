"""AI copilot services (P5-1 read-only context + provider seam; P5-2 synthesize).

Structural rule: nothing in this package may import write-path services
(validation / backtests / strategies / validation_spec / status_machine) or
call ORM write APIs — enforced by ``tests/unit/test_copilot_isolation.py``.
Synthesize rows are written only by the worker task
(``services/worker/tasks/copilot.py``); this package stays read-only.
"""

from services.agent.copilot.context import build_context
from services.agent.copilot.insights import latest_suggestion, list_chat_messages, list_insights
from services.agent.copilot.providers import get_provider

__all__ = [
    "build_context",
    "get_provider",
    "latest_suggestion",
    "list_chat_messages",
    "list_insights",
]
