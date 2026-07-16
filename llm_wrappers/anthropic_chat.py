"""재시도와 OpenAI 대체 호출을 지원하는 Anthropic 비동기 래퍼."""

from __future__ import annotations

import os

from anthropic import AsyncAnthropic

from utils.env_loader import load_env
from utils.llm_retry import (
    AllProvidersFailedError,
    LLMRetryError,
    call_with_retry,
    failure_from,
)

load_env()


class AnthropicChat:
    def __init__(
        self,
        model: str | None = None,
        fallback_to_openai: bool | None = None,
        effort: str | None = None,
        thinking: str | None = None,
        max_attempts: int | None = None,
    ):
        self.model = model or os.environ.get("A2A_MODEL_POLICY", "claude-sonnet-5")
        if fallback_to_openai is None:
            fallback_to_openai = os.environ.get("LLM_ALLOW_FALLBACK", "true").lower() == "true"
        self.fallback_to_openai = fallback_to_openai
        self.max_attempts = max_attempts or int(os.environ.get("LLM_MAX_ATTEMPTS", "3"))
        self.effort = (effort or os.environ.get("ANTHROPIC_EFFORT_POLICY", "low")).lower()
        self.thinking = (thinking or os.environ.get("ANTHROPIC_THINKING_POLICY", "disabled")).lower()
        self.client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    async def __call__(self, prompt: str, max_tokens: int = 1024) -> str:
        async def request():
            request_options = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if self.effort in {"low", "medium", "high", "max"}:
                request_options["output_config"] = {"effort": self.effort}
            if self.thinking == "disabled":
                request_options["thinking"] = {"type": "disabled"}

            return await self.client.messages.create(
                **request_options,
            )

        try:
            response, _attempts = await call_with_retry(
                "Anthropic", request, max_attempts=self.max_attempts
            )
        except LLMRetryError as anthropic_error:
            if not self.fallback_to_openai or not os.environ.get("OPENAI_API_KEY"):
                raise
            print(f"[AnthropicChat] {anthropic_error}. OpenAI 대체 호출을 시도합니다.")
            try:
                from llm_wrappers.openai_chat import OpenAIChat
                return await OpenAIChat(max_attempts=self.max_attempts)(prompt)
            except LLMRetryError as openai_error:
                raise AllProvidersFailedError([
                    failure_from(anthropic_error),
                    failure_from(openai_error),
                ]) from openai_error

        if not response.content:
            return ""
        # content는 text 블록 외에 thinking/tool_use 등 다른 타입도 섞여 올 수 있으므로
        # 첫 블록만 보지 말고 text가 있는 블록을 모두 찾아 이어붙인다.
        parts = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if text:
                parts.append(text)
        return "\n".join(parts)
