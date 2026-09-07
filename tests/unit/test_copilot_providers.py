"""Copilot provider seam tests (P5-2: deepseek default; noop opt-out; no dial-out)."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APIStatusError

from services.agent.copilot import providers as providers_module
from services.agent.copilot.providers import (
    CopilotProviderError,
    DeepSeekProvider,
    NoopProvider,
    get_provider,
)


def _clear_settings(monkeypatch) -> None:
    from services.api.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("STREET_DEEPSEEK_API_KEY", raising=False)


class _FakeOpenAI:
    """Stands in for ``openai.OpenAI``; ``result`` may be text or an exception."""

    def __init__(self, result) -> None:
        self._result = result
        self.init_kwargs: dict = {}
        self.call_kwargs: dict = {}

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.call_kwargs = kwargs
        if isinstance(self._result, BaseException):
            raise self._result
        return self._result


def _install_fake(monkeypatch, result) -> _FakeOpenAI:
    fake = _FakeOpenAI(result)

    def factory(**kwargs):
        fake.init_kwargs = kwargs
        return fake

    monkeypatch.setattr(providers_module, "OpenAI", factory)
    return fake


def _text_response(text: str | None) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_default_provider_is_deepseek_disabled_without_key(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    provider = get_provider()
    assert isinstance(provider, DeepSeekProvider)
    assert provider.name == "deepseek"
    assert provider.enabled is False


def test_noop_opt_out(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_COPILOT_PROVIDER", "noop")
    provider = get_provider()
    assert isinstance(provider, NoopProvider)
    assert provider.enabled is False
    assert provider.synthesize({}) is None


def test_key_enables_deepseek(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    assert get_provider().enabled is True


def test_unknown_provider_fails_loud(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_COPILOT_PROVIDER", "anthropic")
    with pytest.raises(ValueError, match="anthropic"):
        get_provider()


def test_disabled_deepseek_never_constructs_client(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    calls: list = []
    monkeypatch.setattr(providers_module, "OpenAI", lambda **kw: calls.append(kw))
    assert get_provider().synthesize({"total_trials": 47}) is None
    assert calls == []


def test_synthesize_sends_aggregate_messages_and_returns_text(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    fake = _install_fake(monkeypatch, _text_response("  该停了。  "))

    text = get_provider().synthesize({"total_trials": 47, "by_snapshot": []})

    assert text == "该停了。"
    assert fake.init_kwargs["api_key"] == "sk-test"
    assert fake.init_kwargs["base_url"] == "https://api.deepseek.com"
    assert fake.init_kwargs["timeout"] == 60.0
    assert fake.init_kwargs["max_retries"] == 2
    call = fake.call_kwargs
    assert call["model"] == "deepseek-v4-flash"
    assert call["stream"] is False
    assert [m["role"] for m in call["messages"]] == ["system", "user"]
    assert "47" in call["messages"][1]["content"]


def test_copilot_model_env_override(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("STREET_COPILOT_MODEL", "deepseek-v4-pro")
    fake = _install_fake(monkeypatch, _text_response("ok"))
    get_provider().synthesize({"total_trials": 1})
    assert fake.call_kwargs["model"] == "deepseek-v4-pro"


def test_synthesize_empty_content_raises(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    _install_fake(monkeypatch, _text_response(None))
    with pytest.raises(CopilotProviderError, match="空内容"):
        get_provider().synthesize({"total_trials": 1})


def _api_error(status: int) -> APIStatusError:
    request = httpx.Request("POST", DeepSeekProvider.base_url)
    return APIStatusError("boom", response=httpx.Response(status, request=request), body=None)


def test_synthesize_api_errors_are_translated(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    _install_fake(monkeypatch, _api_error(401))
    with pytest.raises(CopilotProviderError, match="401"):
        get_provider().synthesize({"total_trials": 1})

    _install_fake(monkeypatch, _api_error(402))
    with pytest.raises(CopilotProviderError, match="余额不足"):
        get_provider().synthesize({"total_trials": 1})


def test_synthesize_connection_error_translated(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    request = httpx.Request("POST", DeepSeekProvider.base_url)
    _install_fake(monkeypatch, APIConnectionError(message="nope", request=request))
    with pytest.raises(CopilotProviderError, match="无法连接"):
        get_provider().synthesize({"total_trials": 1})


# ------------------------------------------------------------------ suggest


_CANDIDATES = [
    {
        "key": "run_validation:PBO",
        "action": "run_validation",
        "validation_kind": "PBO",
        "reason_code": "never_run",
        "target_version": 1,
    },
    {"key": "discipline:duplicate", "action": "discipline", "reason_code": "duplicate_parameters"},
]


def test_noop_suggest_returns_none(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_COPILOT_PROVIDER", "noop")
    assert get_provider().suggest({}, _CANDIDATES) is None


def test_disabled_deepseek_suggest_never_constructs_client(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    calls: list = []
    monkeypatch.setattr(providers_module, "OpenAI", lambda **kw: calls.append(kw))
    assert get_provider().suggest({}, _CANDIDATES) is None
    assert calls == []


def test_suggest_returns_in_set_pick(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    fake = _install_fake(
        monkeypatch,
        _text_response('{"picked_id": "run_validation:PBO", "reason": "先补 PBO 闸门。"}'),
    )

    pick = get_provider().suggest({"total_trials": 47}, _CANDIDATES)

    assert pick == {"picked_id": "run_validation:PBO", "reason": "先补 PBO 闸门。"}
    roles = [m["role"] for m in fake.call_kwargs["messages"]]
    assert roles == ["system", "user"]
    assert "run_validation:PBO" in fake.call_kwargs["messages"][1]["content"]


def test_suggest_accepts_code_fenced_json(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    _install_fake(
        monkeypatch,
        _text_response(
            '```json\n{"picked_id": "discipline:duplicate", "reason": "先停重复试验。"}\n```'
        ),
    )
    pick = get_provider().suggest({}, _CANDIDATES)
    assert pick["picked_id"] == "discipline:duplicate"


def test_suggest_out_of_set_pick_is_rejected(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    _install_fake(
        monkeypatch,
        _text_response('{"picked_id": "run_validation:DSR", "reason": "随便挑的。"}'),
    )
    with pytest.raises(CopilotProviderError, match="候选之外"):
        get_provider().suggest({}, _CANDIDATES)


def test_suggest_malformed_or_incomplete_reply_is_rejected(monkeypatch) -> None:
    _clear_settings(monkeypatch)
    monkeypatch.setenv("STREET_DEEPSEEK_API_KEY", "sk-test")
    _install_fake(monkeypatch, _text_response("not json"))
    with pytest.raises(CopilotProviderError, match="不是合法 JSON"):
        get_provider().suggest({}, _CANDIDATES)

    _install_fake(monkeypatch, _text_response('{"picked_id": "discipline:duplicate"}'))
    with pytest.raises(CopilotProviderError, match="缺少 reason"):
        get_provider().suggest({}, _CANDIDATES)

    long_text = '{"picked_id": "discipline:duplicate", "reason": "' + ("太长了" * 60) + '"}'
    _install_fake(monkeypatch, _text_response(long_text))
    with pytest.raises(CopilotProviderError, match="超过"):
        get_provider().suggest({}, _CANDIDATES)
