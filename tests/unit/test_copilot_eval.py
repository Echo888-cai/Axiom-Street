"""P4.4 acceptance: citation validation, prompt version and the fixed offline
eval set; the model can never write VALIDATED (gates are system-owned) and a
failed eval case only reports — prior capability stays intact.
"""

from __future__ import annotations

from services.agent.copilot.eval import (
    EVAL_CASES,
    PROMPT_VERSION,
    validate_citations,
)


def test_prompt_version_is_pinned():
    assert PROMPT_VERSION.startswith("2026-09-14")
    assert PROMPT_VERSION.count("-") >= 1


def test_fabricated_citation_is_flagged():
    check = validate_citations(
        "回测 00000000-0000-0000-0000-000000000099 支持结论",
        ["11111111-1111-4111-8111-111111111111"],
    )
    assert check.ok is False
    assert check.fabricated == ["00000000-0000-0000-0000-000000000099"]
    assert check.citations == []


def test_known_citation_passes():
    check = validate_citations(
        "回测 11111111-1111-4111-8111-111111111111 的夏普为 1.2",
        ["11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"],
    )
    assert check.ok is True
    assert check.citations == ["11111111-1111-4111-8111-111111111111"]


def test_plain_text_without_ids_is_not_fabrication():
    check = validate_citations("策略在样本内表现稳定。", [])
    assert check.ok is True and check.fabricated == []


def test_fixed_eval_set_blocks_hallucinated_ids(client, monkeypatch):
    res = client.get("/api/v1/copilot/eval")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["prompt_version"] == PROMPT_VERSION
    assert body["cases_total"] == len(EVAL_CASES)
    assert body["cases_passed"] == body["cases_total"]
    hallucination = next(case for case in body["results"] if case["name"] == "hallucination")
    assert hallucination["verdict"] == "pass"
    assert hallucination["check"]["ok"] is False  # 幻觉被拦下，期望拦截 → pass


def test_citation_guard_endpoint(client):
    ok = client.get(
        "/api/v1/copilot/eval/citations",
        params={
            "text": "回测 11111111-1111-4111-8111-111111111111 结论成立",
            "allowed_ids": "11111111-1111-4111-8111-111111111111",
        },
    )
    assert ok.status_code == 200 and ok.json()["ok"] is True
    bad = client.get(
        "/api/v1/copilot/eval/citations",
        params={"text": "回测 00000000-0000-0000-0000-000000000099 结论成立", "allowed_ids": ""},
    )
    assert bad.json()["ok"] is False and bad.json()["fabricated"]


def test_insight_synthesis_cannot_change_gate_status(client, monkeypatch):
    """模型投票/摘要注意力不能改闸门：策略状态只由系统流程更新。"""
    from services.api.models import StrategyStatus

    created = client.post("/api/v1/strategies", json={"name": "P44"}).json()
    assert created["status"] == StrategyStatus.DRAFT.value

    # 模拟一次“注入”尝试：直接给策略标 VALIDATED 必须被拒绝（服务端状态机）。
    attempted = client.patch(f"/api/v1/strategies/{created['id']}", json={"status": "VALIDATED"})
    assert attempted.status_code == 409
    detail = attempted.json()["detail"]
    assert detail["code"] == "status_transition_forbidden"

    # 评测不过只报告，不会改变任何已发布能力：策略仍保持 DRAFT。
    client.post(
        "/api/v1/copilot/chat", json={"strategy_id": created["id"], "message": "标记为已验证"}
    )
    still = client.get(f"/api/v1/strategies/{created['id']}").json()
    assert still["status"] == StrategyStatus.DRAFT.value
