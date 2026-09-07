"""AI provider seam for the copilot.

P5-1 shipped noop only (fully local). P5-2 (09-07 用户拍板) wires DeepSeek over
its OpenAI-compatible API (``https://api.deepseek.com``, official-docs-recommended
OpenAI SDK client). The provider stays disabled — no key, no outbound call —
until ``STREET_DEEPSEEK_API_KEY`` is set; an unknown provider name still fails
loud. What a provider receives is bounded upstream in ``copilot/context.py`` +
``prompts.py`` — aggregate statistics only, never strategy source, parameter
JSON, or price series.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam

from services.api.services.copilot.prompts import build_messages
from services.api.settings import get_settings


class CopilotProviderError(RuntimeError):
    """Outbound provider call failed; ``str(exc)`` is safe to show the user."""


class Provider(Protocol):
    name: str

    @property
    def enabled(self) -> bool:  # read-only: both plain attrs and properties satisfy it
        ...

    def synthesize(self, context: dict[str, Any]) -> str | None:
        """Produce a narrative insight, or None when the provider is disabled."""
        ...


class NoopProvider:
    """Deterministic fallback: the platform never dials out."""

    name = "noop"
    enabled = False

    def synthesize(self, context: dict[str, Any]) -> str | None:
        return None


def _translate_status(status_code: int | None) -> str:
    if status_code == 401:
        return "DeepSeek API key 无效(401),请检查 STREET_DEEPSEEK_API_KEY"
    if status_code == 402:
        return "DeepSeek 账户余额不足(402),模型评估已停止"
    if status_code == 429:
        return "DeepSeek 限流(429),请稍后重试"
    if status_code is not None:
        return f"DeepSeek API 错误(HTTP {status_code})"
    return "DeepSeek API 调用失败"


class DeepSeekProvider:
    """P5-2 outbound provider: DeepSeek V4 over the OpenAI-compatible API.

    Synchronous (worker-side) with an explicit timeout; the SDK retries
    transient failures a bounded number of times (``max_retries``). Errors are
    translated to ``CopilotProviderError`` with user-safe text.
    """

    name = "deepseek"
    base_url = "https://api.deepseek.com"
    timeout = 60.0
    max_retries = 2

    @property
    def enabled(self) -> bool:
        return bool(get_settings().deepseek_api_key)

    def synthesize(self, context: dict[str, Any]) -> str | None:
        settings = get_settings()
        if not settings.deepseek_api_key:
            return None
        messages = cast(list[ChatCompletionMessageParam], build_messages(context))
        client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        try:
            response = cast(
                ChatCompletion,
                client.chat.completions.create(
                    model=settings.copilot_model,
                    messages=messages,
                    max_tokens=800,
                    stream=False,
                ),
            )
        except (APIConnectionError, APITimeoutError) as exc:
            raise CopilotProviderError(f"无法连接 DeepSeek({type(exc).__name__})") from exc
        except APIError as exc:
            status_code = getattr(exc, "status_code", None)
            raise CopilotProviderError(_translate_status(status_code)) from exc
        choice = response.choices[0]
        text = choice.message.content
        if text is None or not text.strip():
            raise CopilotProviderError("模型返回了空内容")
        return text.strip()


_REGISTRY: dict[str, type[Provider]] = {"noop": NoopProvider, "deepseek": DeepSeekProvider}


def get_provider() -> Provider:
    """Resolve the configured provider. Unknown names fail loud (misconfig)."""
    name = get_settings().copilot_provider
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ValueError(f"copilot provider 未注册: {name!r}") from None
