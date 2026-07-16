"""일반 실행과 교차검증 실행에 맞는 생성 LLM을 선택한다."""

from __future__ import annotations

import os


def generation_provider(default_provider: str) -> str:
    """교차검증 지정값이 있으면 사용하고, 없으면 에이전트 기존 제공자를 유지한다."""
    provider = os.environ.get("GENERATION_PROVIDER", default_provider).lower()
    if provider not in {"openai", "anthropic"}:
        raise ValueError(f"지원하지 않는 생성 제공자: {provider}")
    return provider


def make_generation_chat(default_provider: str, model: str | None = None):
    provider = generation_provider(default_provider)
    attempts = int(os.environ.get("LLM_MAX_ATTEMPTS", "3"))
    if provider == "openai":
        from llm_wrappers.openai_chat import OpenAIChat

        return OpenAIChat(
            model=model or os.environ.get("OPENAI_MODEL", "gpt-5.2"),
            max_attempts=attempts,
        )

    from llm_wrappers.anthropic_chat import AnthropicChat

    return AnthropicChat(
        model=model or os.environ.get("A2A_MODEL_POLICY", "claude-sonnet-5"),
        fallback_to_openai=None,
        max_attempts=attempts,
    )

