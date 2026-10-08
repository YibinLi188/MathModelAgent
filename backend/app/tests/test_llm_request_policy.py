"""Bounded LLM request timeout and retry regression tests."""

import asyncio

import pytest

from app.config.setting import ApiType
from app.core.llm.llm import DEFAULT_MAX_RETRIES, LLM, LLMRequestError


class HangingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def call(self, **_kwargs):
        self.calls += 1
        await asyncio.sleep(60)


class FailingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def call(self, **_kwargs):
        self.calls += 1
        raise RuntimeError("provider unavailable")


def configured_llm() -> LLM:
    return LLM(
        api_type=ApiType.OPENAI_CHAT,
        api_key="test-key",
        model="test-model",
        task_id="test-task",
    )


def test_chat_times_out_each_attempt_and_stops():
    model = configured_llm()
    provider = HangingProvider()
    model.provider = provider  # type: ignore[assignment]

    with pytest.raises(LLMRequestError, match="2 次有界尝试"):
        asyncio.run(
            model.chat(
                history=[{"role": "user", "content": "hello"}],
                max_retries=2,
                retry_delay=0,
                request_timeout_s=0.01,
            )
        )
    assert provider.calls == 2


def test_chat_uses_bounded_default_retry_count():
    model = configured_llm()
    provider = FailingProvider()
    model.provider = provider  # type: ignore[assignment]

    with pytest.raises(LLMRequestError, match="provider unavailable"):
        asyncio.run(
            model.chat(
                history=[{"role": "user", "content": "hello"}],
                retry_delay=0,
            )
        )
    assert provider.calls == DEFAULT_MAX_RETRIES
