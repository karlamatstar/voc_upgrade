"""pytest 실행 결과를 보고서 생성용 구조화 로그로 자동 저장한다."""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent / "reports" / "logs" / "pytest"
_RUN: dict | None = None
_JSON_PATH: Path | None = None
_STARTED_MONOTONIC = 0.0


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_json() -> None:
    if _RUN is None or _JSON_PATH is None:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _JSON_PATH.write_text(
        json.dumps(_RUN, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _run_type(args: list[str]) -> str:
    joined = " ".join(args).lower()
    if "test_agent_unit.py" in joined:
        return "unit"
    if "test_pipeline_e2e.py" in joined:
        return "e2e"
    if "test_llm_judge.py" in joined:
        return "llm_judge_unit"
    if "test_mcp_tools.py" in joined:
        return "mcp"
    if "test_fault_tolerance.py" in joined:
        return "fault_tolerance"
    return "full_or_custom"


def pytest_configure(config) -> None:
    """pytest 시작 즉시 running 상태를 남겨 강제 중단도 구분할 수 있게 한다."""
    global _RUN, _JSON_PATH, _STARTED_MONOTONIC

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    args = [str(arg) for arg in config.invocation_params.args]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _JSON_PATH = LOG_DIR / f"pytest_{run_id}.json"
    _STARTED_MONOTONIC = time.perf_counter()
    _RUN = {
        "schema_version": 1,
        "run_id": run_id,
        "runner": "pytest",
        "run_type": _run_type(args),
        "status": "running",
        "started_at": _now_iso(),
        "finished_at": None,
        "duration_seconds": None,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "working_directory": str(config.invocation_params.dir),
        "arguments": args,
        "counts": {},
        "tests": [],
    }
    _write_json()


def pytest_runtest_logreport(report) -> None:
    """각 테스트의 최종 실행 단계와 실패 근거를 수집한다."""
    if _RUN is None:
        return

    should_record = report.when == "call" or (
        report.when in {"setup", "teardown"} and report.outcome != "passed"
    )
    if not should_record:
        return

    item = {
        "nodeid": report.nodeid,
        "phase": report.when,
        "outcome": report.outcome,
        "duration_seconds": round(float(report.duration), 4),
    }
    if report.outcome != "passed":
        item["detail"] = str(report.longrepr)[:4000]
    _RUN["tests"].append(item)


def pytest_sessionfinish(session, exitstatus) -> None:
    """pytest 종료 시 통과·실패·건너뜀 집계와 사람이 읽는 로그를 함께 남긴다."""
    if _RUN is None or _JSON_PATH is None:
        return

    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = getattr(reporter, "stats", {}) if reporter is not None else {}

    def count(name: str) -> int:
        return len(stats.get(name, []))

    counts = {
        "collected": int(getattr(session, "testscollected", 0)),
        "passed": count("passed"),
        "failed": count("failed"),
        "errors": count("error"),
        "skipped": count("skipped"),
        "xfailed": count("xfailed"),
        "xpassed": count("xpassed"),
    }
    _RUN.update({
        "status": "completed" if int(exitstatus) == 0 else "failed",
        "exit_status": int(exitstatus),
        "finished_at": _now_iso(),
        "duration_seconds": round(time.perf_counter() - _STARTED_MONOTONIC, 3),
        "counts": counts,
    })
    _write_json()

    log_path = _JSON_PATH.with_suffix(".log")
    lines = [
        f"run_id: {_RUN['run_id']}",
        f"run_type: {_RUN['run_type']}",
        f"status: {_RUN['status']}",
        f"started_at: {_RUN['started_at']}",
        f"finished_at: {_RUN['finished_at']}",
        f"duration_seconds: {_RUN['duration_seconds']}",
        f"counts: {json.dumps(counts, ensure_ascii=False)}",
        "",
        "[test results]",
    ]
    for item in _RUN["tests"]:
        lines.append(
            f"{item['outcome'].upper():7} {item['nodeid']} "
            f"({item['duration_seconds']}s, {item['phase']})"
        )
        if item.get("detail"):
            lines.append(item["detail"])
    log_path.write_text("\n".join(lines), encoding="utf-8")

