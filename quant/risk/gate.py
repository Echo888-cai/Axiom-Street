"""Host-side rendering for the in-LEAN risk gate (Phase 6 WP-1).

``LeanQuantEngine`` mounts only ``algo_dir`` into the container, so the pure
engine and adapter must be written there as sibling modules and the stored
strategy code composed with an appended wrapper block. Rendering copies the
exact module source files (never a re-derivation), so the container runs the
identical code the host unit tests exercise.
"""

from __future__ import annotations

import json
from pathlib import Path

_PKG = Path(__file__).resolve().parent


def runtime_files() -> dict[str, str]:
    """Container files to write into ``algo_dir`` next to ``strategy.py``."""
    return {
        "risk_engine.py": (_PKG / "engine.py").read_text(encoding="utf-8"),
        "risk_gate.py": (_PKG / "runtime_gate.py").read_text(encoding="utf-8"),
    }


def compose_strategy_code(user_code: str, class_name: str, risk_config_json: str) -> str:
    """Return ``user_code`` verbatim plus an appended risk-gate wrapper block.

    ``user_code`` is never rewritten. The appended block (executed after the
    user's classes are defined) makes its own directory importable so
    ``risk_gate`` / ``risk_engine`` resolve, then builds a ``<class>RiskGated``
    subclass of the user algorithm and registers it under that name.
    """
    block = f"""
# ---- Axiom risk gate (Phase 6) ----
import json as _axiom_json
import os as _axiom_os
import sys as _axiom_sys
_here = _axiom_os.path.dirname(_axiom_os.path.abspath(__file__))
if _here not in _axiom_sys.path:
    _axiom_sys.path.insert(0, _here)
import risk_gate as _axiom_risk_gate

_axiom_user_cls = globals()[{json.dumps(class_name)}]
_axiom_gated = _axiom_risk_gate.build_gate(
    _axiom_user_cls, {json.dumps(json.dumps(risk_config_json))}
)
globals()[{json.dumps(class_name + "RiskGated")}] = _axiom_gated
"""
    return user_code + block
