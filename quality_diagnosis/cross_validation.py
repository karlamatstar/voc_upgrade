"""A~D 교차검증 실험을 고정 모델 1회 호출 방식으로 실행한다."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import socket
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REPORT_ROOT = ROOT / "quality_diagnosis" / "reports" / "cross_validation"
AGENT_MODULES = (
    "interpreter", "retriever", "summarizer", "evaluator", "critic", "improver"
)
EXPERIMENTS = {
    "A": {"generation": "openai", "judge": "anthropic", "purpose": "기본 교차 품질검증"},
    "B": {"generation": "anthropic", "judge": "openai", "purpose": "모델 역할 변경 검증"},
    "C": {"generation": "openai", "judge": "openai", "purpose": "OpenAI 동일 모델 평가 비교"},
    "D": {"generation": "anthropic", "judge": "anthropic", "purpose": "Anthropic 동일 모델 평가 비교"},
}
CRITERIA_NAMES = (
    "Interpreter 해석 정확성",
    "Retriever 검색 관련성",
    "Summarizer 사실성·요약성",
    "Evaluator 평가 타당성",
    "Critic 위험 탐지력",
    "Improver 실행 가능성",
    "Agent 연계 품질",
    "장애 대응·로그",
    "성능",
)


def experiment_config(experiment: str) -> dict[str, str]:
    key = experiment.upper()
    if key not in EXPERIMENTS:
        raise ValueError(f"지원하지 않는 실험군: {experiment}")
    return {"experiment": key, **EXPERIMENTS[key]}


def experiment_output_dir(experiment: str) -> Path:
    return REPORT_ROOT / experiment.lower()


def build_locked_environment(experiment: str) -> dict[str, str]:
    config = experiment_config(experiment)
    env = os.environ.copy()
    env.update({
        "CROSS_VALIDATION_EXPERIMENT": config["experiment"],
        "GENERATION_PROVIDER": config["generation"],
        "JUDGE_PROVIDER": config["judge"],
        "JUDGE_LOCK_PROVIDER": "1",
        "LLM_MAX_ATTEMPTS": "1",
        "LLM_ALLOW_FALLBACK": "false",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    })
    return env


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def _wait_ports(expected_open: bool, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        states = [_port_open(port) for port in range(6001, 6007)]
        if all(states) if expected_open else not any(states):
            return True
        time.sleep(0.4)
    return False


def _write_run_meta(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _number(value) -> float | None:
    try:
        if value in {"", "N/A", None}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _markdown(value) -> str:
    return str(value or "-").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _case_status(row: dict) -> str:
    if _number(row.get("total")) is not None:
        return "채점 완료"
    if row.get("total") == "N/A":
        return "N/A"
    verdict = row.get("verdict", "")
    if verdict.startswith("PASS"):
        return "PASS(예외처리)"
    if verdict == "pytest 전용":
        return "pytest 전용"
    return "미평가"


def _display_score(row: dict | None) -> str:
    if row is None:
        return "미실행"
    score = _number(row.get("total"))
    return f"{score:.1f}" if score is not None else _case_status(row)


def _update_comparison_report() -> None:
    """A~D 최신 CSV를 20개 케이스 단위로 합치고 그래프용 CSV도 만든다."""
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    cases_path = ROOT / "quality_diagnosis" / "test_cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    case_map = {case["case_id"]: case for case in cases}
    experiment_rows: dict[str, list[dict]] = {}
    by_case: dict[str, dict[str, dict]] = {case["case_id"]: {} for case in cases}

    for key in EXPERIMENTS:
        csv_path = experiment_output_dir(key) / "llm_judge_result.csv"
        if not csv_path.exists():
            experiment_rows[key] = []
            continue
        with csv_path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        experiment_rows[key] = rows
        for row in rows:
            if row.get("case_id"):
                by_case.setdefault(row["case_id"], {})[key] = row

    lines = [
        "# 교차검증 종합 비교보고서", "",
        f"- 최근 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 비교 단위: TC-01~TC-20",
        "- 정식 점수 비교: TC-01~16",
        "- 예외처리 확인: TC-17~18",
        "- pytest 장애 검증 전용: TC-19~20",
        "- 수행시간 집계: TC-01~18 실제 실행(live), pytest 전용 시간 제외", "",
        "## 1. 실험군별 핵심 지표", "",
        "| 실험군 | 생성 모델 | 평가 모델 | 처리 | 정상 채점 | N/A | PASS(예외) | 평균 | 중앙값 | 중앙 수행시간 | 목적 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key, config in EXPERIMENTS.items():
        rows = experiment_rows[key]
        scores = [_number(row.get("total")) for row in rows]
        scores = [score for score in scores if score is not None]
        live_rows = [row for row in rows if row.get("mode") == "live"]
        times = [_number(row.get("total_seconds")) for row in live_rows]
        times = [value for value in times if value is not None]
        na_count = sum(_case_status(row) == "N/A" for row in rows)
        pass_count = sum(_case_status(row) == "PASS(예외처리)" for row in rows)
        average = round(statistics.mean(scores), 1) if scores else "-"
        median_score = round(statistics.median(scores), 1) if scores else "-"
        median_time = f"{statistics.median(times):.2f}초" if times else "-"
        lines.append(
            f"| {key} | {config['generation']} | {config['judge']} | {len(rows)} | "
            f"{len(scores)} | {na_count} | {pass_count} | {average} | {median_score} | "
            f"{median_time} | {config['purpose']} |"
        )

    lines += ["", "## 2. TC-01~20 실험군 교차 비교", ""]
    lines += [
        "| 케이스 | 유형 | 질문 | A | B | C | D | 채점 최고-최저 차이 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for case in cases:
        cid = case["case_id"]
        records = by_case.get(cid, {})
        numeric = [
            score for score in (_number(records.get(key, {}).get("total")) for key in EXPERIMENTS)
            if score is not None
        ]
        gap = f"{max(numeric) - min(numeric):.1f}" if len(numeric) >= 2 else "-"
        lines.append(
            f"| {cid} | {_markdown(case.get('category'))} | {_markdown(case.get('question'))} | "
            + " | ".join(_display_score(records.get(key)) for key in EXPERIMENTS)
            + f" | {gap} |"
        )

    lines += ["", "## 3. 평가 항목별 평균 비교", ""]
    lines += [
        "| 평가 항목 | A | B | C | D |",
        "|---|---:|---:|---:|---:|",
    ]
    for criterion in CRITERIA_NAMES:
        values = []
        for key in EXPERIMENTS:
            criterion_scores = [
                value for value in (_number(row.get(criterion)) for row in experiment_rows[key])
                if value is not None
            ]
            values.append(f"{statistics.mean(criterion_scores):.2f}" if criterion_scores else "-")
        lines.append(f"| {criterion} | " + " | ".join(values) + " |")

    lines += ["", "## 4. 수행시간 비교", ""]
    lines += [
        "| 실험군 | 파이프라인 평균 | Judge 평균 | 전체 평균 | 전체 중앙값 | 최단 | 최장 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key in EXPERIMENTS:
        rows = [row for row in experiment_rows[key] if row.get("mode") == "live"]
        pipeline = [value for value in (_number(row.get("pipeline_seconds")) for row in rows) if value is not None]
        judge = [value for value in (_number(row.get("judge_seconds")) for row in rows) if value is not None]
        total = [value for value in (_number(row.get("total_seconds")) for row in rows) if value is not None]
        fmt = lambda value: f"{value:.2f}초" if value is not None else "-"
        lines.append(
            f"| {key} | {fmt(statistics.mean(pipeline) if pipeline else None)} | "
            f"{fmt(statistics.mean(judge) if judge else None)} | "
            f"{fmt(statistics.mean(total) if total else None)} | "
            f"{fmt(statistics.median(total) if total else None)} | "
            f"{fmt(min(total) if total else None)} | {fmt(max(total) if total else None)} |"
        )

    lines += ["", "## 5. 실험군별 20개 케이스 상세", ""]
    for key, config in EXPERIMENTS.items():
        rows = experiment_rows[key]
        lines += [
            f"### 실험군 {key} — 생성 {config['generation']} / 평가 {config['judge']}", "",
        ]
        if not rows:
            lines += ["아직 실행 결과가 없습니다.", ""]
            continue
        lines += [
            "| TC | 유형 | 상태 | 점수 | 판정 | 파이프라인 | Judge | 전체 | 실제 Judge | API 기록 |",
            "|---|---|---|---:|---|---:|---:|---:|---|---|",
        ]
        for row in rows:
            case = case_map.get(row.get("case_id"), {})
            lines.append(
                f"| {row.get('case_id', '-')} | {_markdown(case.get('category'))} | {_case_status(row)} | "
                f"{_display_score(row)} | {_markdown(row.get('verdict'))} | "
                f"{_markdown(row.get('pipeline_seconds'))} | {_markdown(row.get('judge_seconds'))} | "
                f"{_markdown(row.get('total_seconds'))} | {_markdown(row.get('judge_model'))} | "
                f"{_markdown(row.get('api_attempts'))} |"
            )
        lines += ["", f"#### 실험군 {key} 케이스별 채점·실패 근거", ""]
        for row in rows:
            cid = row.get("case_id", "-")
            lines += [
                f"<details><summary>{cid} — {_display_score(row)} / {_markdown(row.get('verdict'))}</summary>",
                "", _markdown(row.get("rationale")), "", "</details>", "",
            ]

    lines += [
        "## 6. 실행 규칙과 그래프 활용", "",
        "- 각 실험군은 지정된 생성·평가 제공자를 고정한다.",
        "- API 호출은 한 번만 수행하며 재시도하거나 다른 제공자로 대체하지 않는다.",
        "- 생성 또는 평가 API가 실패한 케이스는 N/A로 기록하고 다음 케이스를 계속한다.",
        "- `교차검증_그래프데이터.csv`는 실험군×테스트 케이스 형태의 그래프 원본이다.",
        "- 점수 추이, 실험군 평균, 항목별 평균, 수행시간, N/A 비율 그래프에 바로 사용할 수 있다.",
    ]

    graph_fields = [
        "experiment", "generation_provider", "judge_provider", "case_id", "category",
        "question", "status", "total", "verdict", "immediate_hold",
        "pipeline_seconds", "judge_seconds", "total_seconds", "judge_model", "api_attempts",
        *CRITERIA_NAMES, "rationale",
    ]
    graph_path = REPORT_ROOT / "교차검증_그래프데이터.csv"
    with graph_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=graph_fields)
        writer.writeheader()
        for key, config in EXPERIMENTS.items():
            for row in experiment_rows[key]:
                case = case_map.get(row.get("case_id"), {})
                writer.writerow({
                    "experiment": key,
                    "generation_provider": config["generation"],
                    "judge_provider": config["judge"],
                    "case_id": row.get("case_id", ""),
                    "category": case.get("category", ""),
                    "question": case.get("question", row.get("question", "")),
                    "status": _case_status(row),
                    "total": row.get("total", ""),
                    "verdict": row.get("verdict", ""),
                    "immediate_hold": row.get("immediate_hold", ""),
                    "pipeline_seconds": row.get("pipeline_seconds", ""),
                    "judge_seconds": row.get("judge_seconds", ""),
                    "total_seconds": row.get("total_seconds", ""),
                    "judge_model": row.get("judge_model", ""),
                    "api_attempts": row.get("api_attempts", ""),
                    **{name: row.get(name, "") for name in CRITERIA_NAMES},
                    "rationale": row.get("rationale", ""),
                })

    (REPORT_ROOT / "교차검증_종합비교보고서.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


async def run_experiment(experiment: str, case_id: str | None = None) -> int:
    from utils.env_loader import load_env

    load_env()
    config = experiment_config(experiment)
    env = build_locked_environment(config["experiment"])
    os.environ.update(env)
    output_dir = experiment_output_dir(config["experiment"])
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    agent_log_dir = output_dir / "logs" / "agents" / run_id
    meta_path = output_dir / "logs" / "cross_validation" / f"cross_validation_{run_id}.json"
    meta = {
        "run_id": run_id,
        "experiment": config["experiment"],
        "generation_provider": config["generation"],
        "judge_provider": config["judge"],
        "max_attempts": 1,
        "fallback": False,
        "status": "starting",
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "finished_at": None,
        "output_dir": str(output_dir),
        "error": None,
    }
    _write_run_meta(meta_path, meta)

    processes: list[subprocess.Popen] = []
    log_files = []
    try:
        print(
            f"[교차검증 {config['experiment']}] 생성={config['generation']} · "
            f"평가={config['judge']} · 재시도 없음 · 대체 없음",
            flush=True,
        )
        print(f"[저장 위치] {output_dir}", flush=True)
        if not _wait_ports(False, 12.0):
            raise RuntimeError("6001~6006 포트가 사용 중입니다. 기존 에이전트를 종료한 뒤 다시 실행하세요.")

        agent_log_dir.mkdir(parents=True, exist_ok=True)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for module in AGENT_MODULES:
            log_file = (agent_log_dir / f"{module}.log").open("wb")
            log_files.append(log_file)
            process = subprocess.Popen(
                [sys.executable, "-u", "-m", f"agents.{module}"],
                cwd=ROOT,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
            processes.append(process)

        if not _wait_ports(True, 30.0):
            exited = [
                f"{name}(code={proc.poll()})"
                for name, proc in zip(AGENT_MODULES, processes)
                if proc.poll() is not None
            ]
            raise RuntimeError("에이전트 서버 시작 실패: " + (", ".join(exited) or "포트 준비 시간 초과"))

        meta["status"] = "running"
        _write_run_meta(meta_path, meta)
        sys.path.insert(0, str(ROOT / "quality_diagnosis"))
        import llm_judge

        result = await llm_judge.main(case_id=case_id, output_dir=str(output_dir))
        meta["status"] = "completed"
        return result
    except BaseException as error:
        meta["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        meta["error"] = str(error)
        raise
    finally:
        print("[교차검증] 측정용 에이전트 종료", flush=True)
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for log_file in log_files:
            log_file.close()
        meta["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        _write_run_meta(meta_path, meta)
        _update_comparison_report()


def main() -> int:
    parser = argparse.ArgumentParser(description="VOC A~D 교차검증 실험")
    parser.add_argument("--experiment", required=True, choices=list(EXPERIMENTS))
    parser.add_argument("--case-id", help="선택한 테스트 케이스 한 건만 실행")
    args = parser.parse_args()
    return asyncio.run(run_experiment(args.experiment, args.case_id))


if __name__ == "__main__":
    raise SystemExit(main())
