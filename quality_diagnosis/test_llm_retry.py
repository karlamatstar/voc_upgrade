"""API 재시도·대체 호출·N/A 보고서 처리 테스트."""

import pytest

from utils.llm_retry import LLMRetryError, call_with_retry


class TemporaryError(RuntimeError):
    status_code = 429


def test_retry_succeeds_on_third_attempt():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TemporaryError("rate limit")
        return "성공"

    import asyncio
    value, used = asyncio.run(call_with_retry("Test", operation, base_delay=0))
    assert value == "성공"
    assert used == 3


def test_retry_failure_records_three_attempts():
    async def operation():
        raise TemporaryError("rate limit")

    import asyncio
    with pytest.raises(LLMRetryError) as caught:
        asyncio.run(call_with_retry("Test", operation, base_delay=0))
    assert caught.value.attempts == 3
    assert "3회 시도 실패" in str(caught.value)


def test_non_retryable_auth_error_stops_immediately():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("401 invalid api key")

    import asyncio
    with pytest.raises(LLMRetryError) as caught:
        asyncio.run(call_with_retry("Test", operation, base_delay=0))
    assert attempts == 1
    assert caught.value.attempts == 1


def test_report_excludes_na_from_average(tmp_path, monkeypatch):
    import llm_judge

    monkeypatch.setattr(llm_judge, "REPORTS_DIR", tmp_path)
    rubric = {
        "immediate_hold_conditions": [],
        "verdict_thresholds": [
            {"min_score": 90, "verdict": "배포 가능"},
            {"min_score": 0, "verdict": "배포 보류"},
        ],
    }
    criteria = ["정확성"]
    rows = [
        {"case_id": "OK", "mode": "static", "judge_model": "openai:test",
         "정확성": 80, "total": 80, "verdict": "배포 보류",
         "immediate_hold": False, "api_attempts": "openai:성공", "rationale": "정상"},
        {"case_id": "FAIL", "mode": "static", "judge_model": "N/A",
         "정확성": "N/A", "total": "N/A", "verdict": "미평가(API 실패)",
         "immediate_hold": "", "api_attempts": "모든 API 실패",
         "rationale": "모든 API 재시도 실패"},
    ]

    llm_judge._write_reports(rows, criteria, rubric)
    report = (tmp_path / "quality_score_report.md").read_text(encoding="utf-8")
    assert "평균 점수: 80.0" in report
    assert "API 실패로 미평가(N/A): 1" in report
    assert "모든 API 재시도 실패" in report
