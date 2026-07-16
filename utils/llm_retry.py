"""LLM API 재시도와 실패 정보를 공통 형식으로 제공한다."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class AttemptFailure:
    provider: str
    attempts: int
    error: str


class LLMRetryError(RuntimeError):
    def __init__(self, provider: str, attempts: int, last_error: Exception):
        self.provider = provider
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"{provider} API {attempts}회 시도 실패: {last_error}")


class AllProvidersFailedError(RuntimeError):
    def __init__(
        self,
        failures: list[AttemptFailure],
        message_prefix: str = "모든 API 재시도 실패",
    ):
        self.failures = failures
        detail = "; ".join(
            f"{item.provider} {item.attempts}회 실패({item.error})" for item in failures
        )
        super().__init__(f"{message_prefix}: {detail}")


def is_retryable_error(error: Exception) -> bool:
    """한도·서버·연결 오류는 재시도하고 인증·모델 오류는 즉시 중단한다."""
    status = getattr(error, "status_code", None)
    if status == 429 or (isinstance(status, int) and status >= 500):
        return True
    text = str(error).lower()
    return any(token in text for token in (
        "429", "rate limit", "timeout", "timed out", "connection",
        "temporarily unavailable", "server error", "overloaded", "5xx",
    ))


async def call_with_retry(
    provider: str,
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
) -> tuple[T, int]:
    last_error: Exception | None = None
    attempts = 0
    for attempts in range(1, max_attempts + 1):
        try:
            return await operation(), attempts
        except Exception as error:
            last_error = error
            if not is_retryable_error(error) or attempts >= max_attempts:
                break
            await asyncio.sleep(base_delay * (2 ** (attempts - 1)))
    assert last_error is not None
    raise LLMRetryError(provider, attempts, last_error) from last_error


def failure_from(error: LLMRetryError) -> AttemptFailure:
    return AttemptFailure(error.provider, error.attempts, str(error.last_error))
