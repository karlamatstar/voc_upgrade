"""최종 VOC 산출물을 독립 LLM으로 채점하고 보고서 2종을 생성한다."""

from __future__ import annotations

import asyncio
import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qa_test_utils import REPORTS_DIR, all_agents_running, load_json, pb2_generated  # noqa: E402
from judge_prompt import build_judge_prompt, decide_verdict, parse_judge_response  # noqa: E402


ACTIVE_REPORTS_DIR = REPORTS_DIR
DEFAULT_REPORTS_DIR = REPORTS_DIR
JUDGE_LOG_DIR = ACTIVE_REPORTS_DIR / "logs" / "llm_judge"


def configure_output_dir(path: str | None) -> None:
    """단일 케이스 실행 시 기존 전체 보고서와 분리된 저장 위치를 설정한다."""
    global ACTIVE_REPORTS_DIR, JUDGE_LOG_DIR
    ACTIVE_REPORTS_DIR = Path(path).resolve() if path else REPORTS_DIR
    JUDGE_LOG_DIR = ACTIVE_REPORTS_DIR / "logs" / "llm_judge"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class JudgeRunLog:
    """보고서 생성기가 읽을 수 있는 LLM Judge 실행 로그를 관리한다."""

    def __init__(self, cases: list[dict]):
        self.enabled_ids = {
            case["case_id"] for case in cases if case.get("judge_enabled", False)
        }
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        JUDGE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.path = JUDGE_LOG_DIR / f"llm_judge_{run_id}.json"
        self.data = {
            "schema_version": 1,
            "run_id": run_id,
            "runner": "llm_judge",
            "status": "running",
            "started_at": _now_iso(),
            "finished_at": None,
            "configured_models": None,
            "experiment": os.environ.get("CROSS_VALIDATION_EXPERIMENT"),
            "generation_provider": os.environ.get("GENERATION_PROVIDER"),
            "judge_provider": os.environ.get("JUDGE_PROVIDER"),
            "fixed_provider": os.environ.get("JUDGE_LOCK_PROVIDER") == "1",
            "case_counts": {
                "total_defined": len(cases),
                "judge_target": len(self.enabled_ids),
                "processed": 0,
                "scored": 0,
                "na": 0,
                "not_scored": 0,
            },
            "case_results": [],
            "outputs": {
                "csv": str(ACTIVE_REPORTS_DIR / "llm_judge_result.csv"),
                "markdown": str(ACTIVE_REPORTS_DIR / "quality_score_report.md"),
            },
            "error": None,
        }
        self._write()

    def _write(self) -> None:
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def set_models(self, configured_models: str) -> None:
        self.data["configured_models"] = configured_models
        self._write()

    def update(self, rows: list[dict]) -> None:
        target_rows = [row for row in rows if row.get("case_id") in self.enabled_ids]
        scored = [row for row in target_rows if isinstance(row.get("total"), (int, float))]
        na_rows = [row for row in target_rows if row.get("total") == "N/A"]
        self.data["case_counts"].update({
            "processed": len(target_rows),
            "scored": len(scored),
            "na": len(na_rows),
            "not_scored": len(target_rows) - len(scored) - len(na_rows),
        })
        self.data["case_results"] = [
            {
                "case_id": row.get("case_id"),
                "mode": row.get("mode"),
                "judge_model": row.get("judge_model"),
                "total": row.get("total"),
                "verdict": row.get("verdict"),
                "immediate_hold": row.get("immediate_hold"),
                "api_attempts": row.get("api_attempts"),
                "pipeline_seconds": row.get("pipeline_seconds"),
                "judge_seconds": row.get("judge_seconds"),
                "total_seconds": row.get("total_seconds"),
                "rationale": row.get("rationale"),
            }
            for row in rows
        ]
        self._write()

    def finish(self, status: str, error: str | None = None) -> None:
        self.data["status"] = status
        self.data["finished_at"] = _now_iso()
        self.data["error"] = error
        self._write()


@dataclass(frozen=True)
class JudgeCallResult:
    text: str
    provider: str
    attempts: str


class JudgeLLM:
    """우선 제공자 실패 시 두 번째 제공자까지 호출한다."""

    def __init__(self, providers: list[tuple[str, str, object]], fixed_provider: bool = False):
        self.providers = providers
        self.fixed_provider = fixed_provider

    async def __call__(self, prompt: str) -> JudgeCallResult:
        from utils.llm_retry import AllProvidersFailedError, LLMRetryError, failure_from

        failures = []
        notes = []
        for provider, model, llm in self.providers:
            try:
                if provider == "anthropic":
                    # 2048 토큰으로는 immediate_hold처럼 hold_reason·rationale이
                    # 길어지는 케이스에서 JSON이 중간에 잘려 파싱 실패로 이어졌다.
                    text = await llm(prompt, max_tokens=4096)
                else:
                    text = await llm(
                        prompt,
                        max_tokens=int(os.environ.get("JUDGE_OPENAI_MAX_COMPLETION_TOKENS", "2000")),
                    )
                notes.append(f"{provider}:성공")
                return JudgeCallResult(text, f"{provider}:{model}", "; ".join(notes))
            except LLMRetryError as error:
                failures.append(failure_from(error))
                notes.append(f"{provider}:{error.attempts}회 실패")
        prefix = "고정 평가 모델 API 1회 호출 실패" if self.fixed_provider else "모든 API 재시도 실패"
        raise AllProvidersFailedError(failures, message_prefix=prefix)


def make_judge_llm():
    """키가 있는 제공자를 설정 순서대로 구성한다."""
    preferred = os.environ.get("JUDGE_PROVIDER", "anthropic").lower()
    if preferred not in {"anthropic", "openai"}:
        preferred = "anthropic"

    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    providers = []

    locked = os.environ.get("JUDGE_LOCK_PROVIDER") == "1"
    order = [preferred] if locked else [
        preferred, "openai" if preferred == "anthropic" else "anthropic"
    ]
    for provider in order:
        if provider == "anthropic" and has_anthropic:
            from llm_wrappers.anthropic_chat import AnthropicChat
            default_model = os.environ.get("A2A_MODEL_POLICY", "claude-sonnet-5")
            model = (
                os.environ.get("JUDGE_ANTHROPIC_MODEL", default_model)
                if locked
                else os.environ.get("JUDGE_MODEL", default_model)
                if provider == preferred
                else default_model
            )
            providers.append((
                provider,
                model,
                AnthropicChat(
                    model=model,
                    fallback_to_openai=False,
                    effort=os.environ.get("ANTHROPIC_EFFORT_JUDGE", "low"),
                    thinking=os.environ.get("ANTHROPIC_THINKING_JUDGE", "disabled"),
                    max_attempts=int(os.environ.get("LLM_MAX_ATTEMPTS", "3")),
                ),
            ))
        elif provider == "openai" and has_openai:
            from llm_wrappers.openai_chat import OpenAIChat
            default_model = os.environ.get("OPENAI_MODEL", "gpt-5.2")
            model = (
                os.environ.get("JUDGE_OPENAI_MODEL", default_model)
                if locked
                else os.environ.get("JUDGE_MODEL", default_model)
                if provider == preferred
                else default_model
            )
            providers.append((
                provider,
                model,
                OpenAIChat(
                    model=model,
                    max_attempts=int(os.environ.get("LLM_MAX_ATTEMPTS", "3")),
                ),
            ))

    if not providers:
        raise RuntimeError("ANTHROPIC_API_KEY 또는 OPENAI_API_KEY가 필요합니다.")

    label = " -> ".join(f"{provider}:{model}" for provider, model, _llm in providers)
    return JudgeLLM(providers, fixed_provider=locked), label


async def get_analysis(case: dict) -> tuple[str | None, str]:
    mode = case.get("judge_mode", "live")
    if mode == "static":
        return case["analysis"], "static"
    if not pb2_generated():
        return None, "SKIP: voc_pb2.py 미생성 (voc.proto 컴파일 필요)"
    if not all_agents_running():
        return None, "SKIP: 6개 에이전트 서버(6001~6006) 미가동"

    from qa_test_utils import get_runtime
    # expect_no_data가 아닌(즉 검색이 정상적으로 성공해야 하는) 케이스에서만
    # 원본 질문 단어를 안전망 필터로 함께 보낸다. expect_no_data 케이스는 이
    # 안전망을 걸지 않아 "관련 데이터 없음"이 정직하게 나오는지 순수하게 검증한다.
    extra_filters = None
    if not case.get("expect_no_data"):
        import grpc_server
        extra_filters = grpc_server._extract_fallback_tokens(case["question"])

    started = time.perf_counter()
    out = await get_runtime().run_with_question(
        question=case["question"], csv_path=None, timeout=180.0,
        extra_filters=extra_filters,
    )
    elapsed = time.perf_counter() - started
    if not out.get("ok"):
        # out["message"]는 성공/실패와 무관하게 항상 같은 고정 문구라 원인 파악에
        # 쓸모가 없다. 대신 trace(Retriever count 등 단계별 실제 기록)와
        # intent_json(Interpreter가 실제로 뽑은 필터)을 사유에 남긴다.
        trace = out.get("trace") or "(trace 없음)"
        intent = out.get("intent_json") or "(intent 없음)"
        # expect_no_data=true인 케이스에서 Retriever가 실제로 0건을 찾았다면
        # 이건 실패가 아니라 설계된 정답이다("관련 데이터 없음"을 올바르게
        # 인지해야 하는 케이스). 원인 불명 SKIP과 구분해서 PASS_NO_DATA로 표시한다.
        if case.get("expect_no_data") and "Retriever:count=0" in trace:
            return None, f"PASS_NO_DATA({elapsed:.1f}초) - trace={trace} | intent={intent}"
        return None, f"SKIP: 파이프라인 실패({elapsed:.1f}초) - trace={trace} | intent={intent}"
    analysis = (
        f"[Interpreter 의도]\n{out.get('intent_json', '{}')}\n\n"
        f"[Retriever 및 Agent 연계 추적]\n{out.get('trace', '')}\n\n"
        f"[Summarizer 요약]\n{out.get('summary', '')}\n\n"
        f"[Evaluator 평가]\n{out.get('eval_json', '{}')}\n\n"
        f"[Critic 검토]\n{out.get('summary_critic_json', '{}')}\n\n"
        f"[Improver 정책 개선안]\n{out.get('policy', '')}\n\n"
        f"[전체 응답시간]\n{elapsed:.2f}초"
    )
    return analysis, "live"


def _empty_row(
    cid, mode, judge_model, criteria_names, verdict, rationale,
    question="", total="", pipeline_seconds=None, judge_seconds=None,
    total_seconds=None,
):
    value = "N/A" if total == "N/A" else ""
    return {
        "case_id": cid,
        "question": question,
        "mode": mode,
        "judge_model": judge_model,
        **{name: value for name in criteria_names},
        "total": total,
        "verdict": verdict,
        "immediate_hold": "",
        "api_attempts": rationale if total == "N/A" else "",
        "pipeline_seconds": pipeline_seconds,
        "judge_seconds": judge_seconds,
        "total_seconds": total_seconds,
        "rationale": rationale,
        "analysis": "",
    }


async def _run_judge(cases: list[dict], run_log: JudgeRunLog) -> int:
    from utils.llm_retry import AllProvidersFailedError

    rubric = load_json("judge_rubric.json")
    judge_llm, configured_models = make_judge_llm()
    run_log.set_models(configured_models)
    print(f"[LLM Judge] 호출 순서: {configured_models}")

    criteria_names = [criterion["name"] for criterion in rubric["criteria"]]
    rows = []
    experiment = os.environ.get("CROSS_VALIDATION_EXPERIMENT", "")
    generation_provider = os.environ.get("GENERATION_PROVIDER", "")
    generation_model = (
        os.environ.get("OPENAI_MODEL", "gpt-5.2")
        if generation_provider == "openai"
        else os.environ.get("A2A_MODEL_POLICY", "claude-sonnet-5")
        if generation_provider == "anthropic"
        else ""
    )

    def save() -> None:
        """지금까지 처리된 케이스만으로 리포트를 즉시 갱신한다.

        중간에 중지되거나 크래시해도 마지막으로 완료된 케이스까지는
        디스크에 남도록, 케이스 하나가 끝날 때마다 매번 호출한다.
        """
        for row in rows:
            row.setdefault("experiment", experiment)
            row.setdefault("generation_provider", generation_provider)
            row.setdefault("generation_model", generation_model)
        _write_reports(rows, criteria_names, rubric)
        run_log.update(rows)

    for case in cases:
        cid = case["case_id"]
        mode = case.get("judge_mode", "live")
        case_started = time.perf_counter()
        print(f"\n=== {cid} ({mode}) ===")
        if not case.get("judge_enabled", False):
            note = "pytest 장애 검증 전용 케이스 - LLM Judge 자동 실행 제외"
            print(f"  {note}")
            total_seconds = time.perf_counter() - case_started
            rows.append(_empty_row(
                cid, mode, "-", criteria_names, "pytest 전용", note,
                question=case["question"], total_seconds=total_seconds,
            ))
            save()
            continue
        print(f"  [1/2] {cid} 6개 에이전트 파이프라인 진행 중...", flush=True)
        pipeline_started = time.perf_counter()
        analysis, note = await get_analysis(case)
        pipeline_seconds = time.perf_counter() - pipeline_started
        print(f"  [1/2] {cid} 파이프라인 완료 ({pipeline_seconds:.2f}초)", flush=True)
        if analysis is None:
            print(f"  {note}")
            # PASS_NO_DATA: expect_no_data 케이스에서 Retriever가 실제로 0건을
            # 찾은, 설계상 정답인 상황. 일반 "미평가"와 구분해서 표시한다.
            is_no_data = note.startswith("PASS_NO_DATA")
            is_cross_failure = bool(experiment) and not is_no_data
            verdict = (
                "PASS (예외처리)" if is_no_data
                else "미평가(파이프라인 실패)" if is_cross_failure
                else "미평가"
            )
            total_seconds = time.perf_counter() - case_started
            print(f"  [완료] {cid} 전체 소요시간 {total_seconds:.2f}초", flush=True)
            row = _empty_row(
                cid, mode, configured_models, criteria_names, verdict, note,
                question=case["question"], pipeline_seconds=pipeline_seconds,
                judge_seconds=0.0, total_seconds=total_seconds,
                total="N/A" if is_cross_failure else "",
            )
            if is_cross_failure:
                row["api_attempts"] = "생성 파이프라인 실패, 대체 없음"
            rows.append(row)
            save()
            continue

        expected = {
            "expected_intent": case.get("expected_intent", ""),
            "expected_keywords": case.get("expected_keywords", []),
            "required_output": case.get("required_output", []),
            "prohibited_output": case.get("prohibited_output", []),
        }
        prompt_analysis = f"[테스트 기대 결과]\n{expected}\n\n{analysis}"
        prompt = build_judge_prompt(case["question"], prompt_analysis, rubric)
        print(f"  [2/2] {cid} 독립 LLM Judge 채점 진행 중...", flush=True)
        judge_started = time.perf_counter()
        try:
            call_result = await judge_llm(prompt)
        except AllProvidersFailedError as error:
            judge_seconds = time.perf_counter() - judge_started
            total_seconds = time.perf_counter() - case_started
            reason = str(error)
            print(f"  N/A - {reason}")
            print(f"  [2/2] {cid} Judge 실패 ({judge_seconds:.2f}초)", flush=True)
            print(f"  [완료] {cid} 전체 소요시간 {total_seconds:.2f}초", flush=True)
            rows.append(_empty_row(
                cid, mode, "N/A", criteria_names,
                "미평가(API 실패)", reason, question=case["question"], total="N/A",
                pipeline_seconds=pipeline_seconds, judge_seconds=judge_seconds,
                total_seconds=total_seconds,
            ))
            save()
            continue

        judge_seconds = time.perf_counter() - judge_started
        total_seconds = time.perf_counter() - case_started
        print(f"  [2/2] {cid} Judge 완료 ({judge_seconds:.2f}초)", flush=True)
        print(f"  [완료] {cid} 전체 소요시간 {total_seconds:.2f}초", flush=True)

        result = parse_judge_response(call_result.text, rubric)
        if result is None:
            print("  채점 응답 파싱 실패")
            print(f"  └ 원본 응답 앞부분: {call_result.text[:400]!r}")
            row = _empty_row(
                cid, mode, call_result.provider, criteria_names,
                "파싱 실패", call_result.text[:2000], question=case["question"],
            )
            row["api_attempts"] = call_result.attempts
            row["pipeline_seconds"] = pipeline_seconds
            row["judge_seconds"] = judge_seconds
            row["total_seconds"] = total_seconds
            rows.append(row)
            save()
            continue

        verdict = decide_verdict(result["total"], result["immediate_hold"], rubric)
        print(f"  총점 {result['total']}점 → {verdict}")
        rows.append({
            "case_id": cid,
            "question": case["question"],
            "mode": mode,
            "judge_model": call_result.provider,
            **result["scores"],
            "total": result["total"],
            "verdict": verdict,
            "immediate_hold": result["immediate_hold"],
            "api_attempts": call_result.attempts,
            "pipeline_seconds": round(pipeline_seconds, 2),
            "judge_seconds": round(judge_seconds, 2),
            "total_seconds": round(total_seconds, 2),
            "rationale": result["rationale"],
            "analysis": analysis,  # 채점 대상이 된 실제 파이프라인 답변 원문
        })
        save()

    csv_path = ACTIVE_REPORTS_DIR / "llm_judge_result.csv"
    md_path = ACTIVE_REPORTS_DIR / "quality_score_report.md"
    print(f"\n보고서 저장 완료(케이스마다 갱신됨):\n  {csv_path}\n  {md_path}")
    run_log.finish("completed")
    return 0


async def main(case_id: str | None = None, output_dir: str | None = None) -> int:
    """LLM Judge 실행과 별도로 실행 상태 로그를 항상 보존한다."""
    configure_output_dir(output_dir)
    cases = load_json("test_cases.json")["cases"]
    if case_id:
        cases = [case for case in cases if case.get("case_id") == case_id]
        if not cases:
            raise ValueError(f"존재하지 않는 테스트 케이스: {case_id}")
    run_log = JudgeRunLog(cases)
    try:
        return await _run_judge(cases, run_log)
    except BaseException as error:
        interrupted = isinstance(error, (KeyboardInterrupt, asyncio.CancelledError))
        run_log.finish("interrupted" if interrupted else "failed", str(error))
        raise


def _format_case_detail(row: dict, criteria_names: list[str], max_by_name: dict[str, int]) -> str:
    """케이스 하나의 항목별 점수와 채점 근거를 마크다운 블록으로 만든다."""
    lines = [f"### {row['case_id']} — {row['verdict']} (총점: {row['total']})", ""]
    lines.append(f"- 질문: {row.get('question') or '-'}")
    lines.append(
        f"- 모드: {row['mode']} · 채점 모델: {row['judge_model']} · API 시도: {row.get('api_attempts') or '-'}"
    )
    pipeline_seconds = row.get("pipeline_seconds")
    judge_seconds = row.get("judge_seconds")
    total_seconds = row.get("total_seconds")
    lines.append(
        "- 수행시간: "
        f"파이프라인 {pipeline_seconds if pipeline_seconds is not None else '-'}초 · "
        f"Judge {judge_seconds if judge_seconds is not None else '-'}초 · "
        f"전체 {total_seconds if total_seconds is not None else '-'}초"
    )
    if row.get("immediate_hold") is True:
        lines.append("- ⚠ 즉시 보류 조건에 해당함")

    score_bits = []
    for name in criteria_names:
        value = row.get(name, "")
        if value in ("", None):
            score_bits.append(f"{name} 미평가")
        elif value == "N/A":
            score_bits.append(f"{name} N/A")
        else:
            score_bits.append(f"{name} {value}/{max_by_name.get(name, '?')}")
    lines.append("- 항목별 점수: " + " · ".join(score_bits))
    lines.append(f"- 채점 근거: {row.get('rationale') or '-'}")
    lines.append("")

    analysis = row.get("analysis") or ""
    if analysis:
        lines.append("<details><summary>실제 답변(파이프라인 출력 원문) 펼치기</summary>")
        lines.append("")
        lines.append("```")
        lines.append(analysis)
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")
    return "\n".join(lines)


def _safe_write(path: Path, write_fn) -> None:
    """엑셀 등에서 리포트 파일을 열어둬서 쓰기 권한이 거부돼도 전체 실행이
    죽지 않도록 한다. 케이스마다 저장을 시도하는 구조라, 이번 시도가 막혀도
    다음 케이스가 끝난 뒤 재시도에서 다시 쓰이므로 데이터 유실은 없다.
    """
    try:
        write_fn()
    except PermissionError:
        print(f"  ⚠ {path.name} 저장 실패(파일이 다른 프로그램에서 열려 있는 것으로 보임) - 다음 케이스에서 재시도합니다")


def _write_reports(rows, criteria_names, rubric):
    # 단위 테스트가 REPORTS_DIR만 임시 경로로 교체하는 경우에도 실제 보고서를
    # 덮어쓰지 않도록, 출력 경로를 명시하지 않은 상태라면 변경된 REPORTS_DIR을 따른다.
    reports_dir = (
        REPORTS_DIR
        if ACTIVE_REPORTS_DIR == DEFAULT_REPORTS_DIR and REPORTS_DIR != DEFAULT_REPORTS_DIR
        else ACTIVE_REPORTS_DIR
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    csv_path = reports_dir / "llm_judge_result.csv"
    fieldnames = [
        "experiment", "generation_provider", "generation_model",
        "case_id", "question", "mode", "judge_model", *criteria_names,
        "total", "verdict", "immediate_hold", "api_attempts",
        "pipeline_seconds", "judge_seconds", "total_seconds", "rationale", "analysis",
    ]

    def _write_csv():
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    _safe_write(csv_path, _write_csv)

    scored = [row for row in rows if isinstance(row["total"], (int, float))]
    api_failed = [row for row in rows if row["total"] == "N/A"]
    # PASS(예외처리): expect_no_data 케이스가 실제로 데이터 없음을 정상적으로
    # 인지한 경우. 점수를 매길 대상이 없으므로 평균 계산에는 포함하지 않되,
    # 원인 불명 "미평가"와는 구분해서 별도로 보여준다.
    pass_no_data = [row for row in rows if row["verdict"] == "PASS (예외처리)"]
    average = round(sum(float(row["total"]) for row in scored) / len(scored), 1) if scored else None
    any_hold = any(row.get("immediate_hold") is True for row in scored)

    if average is None:
        decision = "판정 보류 (평가된 케이스 없음 — API 및 에이전트 상태 확인 필요)"
    elif any_hold:
        decision = "배포 보류 (즉시 보류 조건 발생)"
    else:
        decision = decide_verdict(average, False, rubric)

    lines = [
        "# 품질 점수 보고서 (Quality Score Report)", "",
        f"- 실행 일시: {now}",
        f"- 실험군: {os.environ.get('CROSS_VALIDATION_EXPERIMENT') or '일반 실행'}",
        f"- 생성 모델: {os.environ.get('GENERATION_PROVIDER') or '기존 혼합 구성'}",
        f"- 평가 모델: {os.environ.get('JUDGE_PROVIDER') or '환경설정 우선순위'}",
        f"- 전체 케이스: {len(rows)}",
        f"- 정상 평가: {len(scored)}",
        f"- PASS(예외처리, 평균 제외): {len(pass_no_data)}",
        f"- API 실패로 미평가(N/A): {len(api_failed)}", "",
        "| 케이스 | " + " | ".join(criteria_names) + " | 총점 | 판정 |",
        "| :--- |" + " ---: |" * len(criteria_names) + " ---: | :--- |",
    ]
    for row in rows:
        scores = " | ".join(str(row[name]) for name in criteria_names)
        lines.append(f"| {row['case_id']} | {scores} | {row['total']} | {row['verdict']} |")
    lines += ["", f"**평균 점수: {average if average is not None else '미평가'}** (PASS(예외처리) {len(pass_no_data)}건 제외)"]
    if pass_no_data:
        lines += ["", "## PASS(예외처리) 케이스 - 데이터 없음을 정상적으로 인지함 (평균 점수 미포함)", ""]
        lines.extend(f"- {row['case_id']}: {row['rationale']}" for row in pass_no_data)
    if api_failed:
        failure_title = (
            "API 1회 호출 실패 내역 (요약)"
            if os.environ.get("CROSS_VALIDATION_EXPERIMENT")
            else "API 재시도 실패 내역 (요약)"
        )
        lines += ["", f"## {failure_title}", ""]
        lines.extend(f"- {row['case_id']}: {row['rationale']}" for row in api_failed)

    # ---- 케이스별 상세: 항목별 점수와 채점 근거를 그대로 남긴다 ----
    max_by_name = {c["name"]: c["max_score"] for c in rubric.get("criteria", [])}
    lines += ["", "---", "", "## 케이스별 상세 (항목별 점수 · 채점 근거)", ""]
    for row in rows:
        lines.append(_format_case_detail(row, criteria_names, max_by_name))

    # ---- 최종 배포 판정 (별도 파일로 나누지 않고 이 보고서에 합침) ----
    lines += [
        "---", "",
        "## 최종 배포 판정", "",
        f"- 평가 케이스: {len(scored)} / {len(rows)}",
        f"- PASS(예외처리, 평균 제외): {len(pass_no_data)}",
        f"- API 실패로 미평가(N/A): {len(api_failed)}",
        f"- 평균 점수: {average if average is not None else '미평가'}", "",
        f"### 최종 판정: **{decision}**", "",
        "판정 기준: 90+ 배포 가능 / 80~89 조건부 배포 / 70~79 개선 후 재시험 / ~69 배포 보류",
    ]
    md_path = reports_dir / "quality_score_report.md"
    _safe_write(md_path, lambda: md_path.write_text("\n".join(lines), encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VOC 독립 LLM Judge")
    parser.add_argument("--case-id", help="한 건만 실행할 테스트 케이스 ID (예: TC-01)")
    parser.add_argument("--output-dir", help="CSV·Markdown·JSON 로그를 저장할 별도 폴더")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(case_id=args.case_id, output_dir=args.output_dir)))
