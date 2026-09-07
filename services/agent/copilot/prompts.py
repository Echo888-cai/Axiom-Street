"""Outbound prompt assembly for copilot synthesize (P5-2).

Pure function layer between the read-only context (aggregate statistics only)
and the model provider. Lives in the copilot package, so the isolation locks
apply: nothing here may import write-path services, call ORM write APIs, or so
much as reference research-IP / market columns. The model only ever sees what
``build_context`` emits plus this module's instructions.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

MAX_NARRATIVE_CHARS = 180

_SYSTEM = (
    "你是 Axiom Street 量化研究平台的守门人助手。你的唯一职责:依据给定的研究"
    "事实,在证据表明用户正在自欺(反复试错、数据窥探、在已被取代的数据快照上"
    "继续试验、参数重复、闸门迟迟不过)时,诚实、直接地劝用户停下来;证据不足"
    "时如实说明没有劝停理由。"
    "硬规则:① 只能引用给定事实里的数字,严禁编造任何数字;② 不知道或看不准就"
    "明说;③ 不评价策略质量,不给改进建议(那是别的功能);④ 用中文,≤"
    f"{MAX_NARRATIVE_CHARS} 字,2–6 句平实的话,不要标题、列表或代码。"
)


def _clean(value: Any) -> Any:
    if isinstance(value, (UUID, datetime, date)):
        return str(value)
    if isinstance(value, Enum):
        return _clean(value.value)
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def build_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    """Render the aggregate context into one system + one user message.

    The payload is deterministic JSON of the read-only context — strategy
    metadata, trial-ledger counts by snapshot, gate outcomes. No strategy
    source, parameter configuration, or market series can appear here because
    ``context.py`` never selects those columns.
    """
    facts = {k: _clean(v) for k, v in context.items() if v is not None}
    user = (
        "以下是当前研究上下文(仅聚合统计,已剔除策略代码、参数与行情):\n"
        + json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n\n请根据这些事实判断:该停了吗?"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]


# --- P5-3 suggest mode: pick one actionable card, never invent one ---

_MAX_SUGGEST_REASON_CHARS = 120

_SUGGEST_SYSTEM = (
    "你是 Axiom Street 量化研究平台的助手。下面的候选建议由平台确定性规则生成,"
    "每条都来自真实研究上下文且可执行;纪律/指引类候选同样基于真实台账事实。"
    "你的唯一任务:在候选中挑一个你判断当下最该采取的动作,给一句简短中文理由。"
    '硬规则:① 只能从候选里挑一个,输出 JSON {"picked_id":"...","reason":"..."};'
    "② reason 只能引用候选本身给出的信息(类型/闸门/版本),"
    f"≤{_MAX_SUGGEST_REASON_CHARS} 字,严禁编造数字、动作或候选外的建议;"
    "③ 不要输出候选以外的任何字段。"
)


def build_suggest_messages(candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Render the deterministic candidate cards into one system + one user msg.

    Candidates carry only machine card metadata (key/action/kind/version) —
    never strategy source, parameter values, or price series. The model is
    confined to this set by construction; membership is enforced again on the
    reply (``providers.DeepSeekProvider.suggest``).
    """
    summaries = [
        {
            "key": c["key"],
            "action": c.get("action"),
            "kind": c.get("validation_kind"),
            "reason_code": c.get("reason_code"),
            "version": c.get("target_version"),
        }
        for c in candidates
        if c.get("key")
    ]
    user = (
        "候选建议:\n"
        + json.dumps(summaries, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + '\n\n请返回 JSON:{"picked_id": "<候选 key>", "reason": "<中文理由>"}。'
    )
    return [{"role": "system", "content": _SUGGEST_SYSTEM}, {"role": "user", "content": user}]
