"""재시도를 지원하는 OpenAI 비동기 래퍼."""

from __future__ import annotations

import os

from openai import AsyncOpenAI

from utils.env_loader import load_env
from utils.llm_retry import call_with_retry

load_env()


class OpenAIChat:
    def __init__(self, model: str | None = None, max_attempts: int | None = None):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5.2")
        self.max_attempts = max_attempts or int(os.environ.get("LLM_MAX_ATTEMPTS", "3"))
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    async def __call__(self, prompt: str, max_tokens: int | None = None) -> str:
        output_limit = max_tokens or int(os.environ.get("OPENAI_MAX_COMPLETION_TOKENS", "900"))

        async def request():
            return await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "none"),
                verbosity=os.environ.get("OPENAI_VERBOSITY", "low"),
                max_completion_tokens=output_limit,
            )

        response, _attempts = await call_with_retry(
            "OpenAI", request, max_attempts=self.max_attempts
        )
        return response.choices[0].message.content or ""
