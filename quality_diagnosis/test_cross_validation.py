"""교차검증 설정과 고정 제공자 규칙을 API 호출 없이 검증한다."""

from pathlib import Path
import asyncio
import csv


def test_experiment_matrix_has_four_fixed_groups():
    from cross_validation import EXPERIMENTS

    assert EXPERIMENTS == {
        "A": {"generation": "openai", "judge": "anthropic", "purpose": "기본 교차 품질검증"},
        "B": {"generation": "anthropic", "judge": "openai", "purpose": "모델 역할 변경 검증"},
        "C": {"generation": "openai", "judge": "openai", "purpose": "OpenAI 동일 모델 평가 비교"},
        "D": {"generation": "anthropic", "judge": "anthropic", "purpose": "Anthropic 동일 모델 평가 비교"},
    }


def test_cross_validation_uses_separate_a_to_d_folders():
    from cross_validation import experiment_output_dir

    assert [experiment_output_dir(key).name for key in "ABCD"] == ["a", "b", "c", "d"]
    assert all(isinstance(experiment_output_dir(key), Path) for key in "ABCD")


def test_locked_environment_disables_retry_and_fallback(monkeypatch):
    from cross_validation import build_locked_environment

    monkeypatch.setenv("SENTINEL", "kept")
    env = build_locked_environment("B")
    assert env["GENERATION_PROVIDER"] == "anthropic"
    assert env["JUDGE_PROVIDER"] == "openai"
    assert env["JUDGE_LOCK_PROVIDER"] == "1"
    assert env["LLM_MAX_ATTEMPTS"] == "1"
    assert env["LLM_ALLOW_FALLBACK"] == "false"
    assert env["SENTINEL"] == "kept"


def test_locked_judge_configures_only_requested_provider(monkeypatch):
    import llm_judge

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("JUDGE_PROVIDER", "openai")
    monkeypatch.setenv("JUDGE_LOCK_PROVIDER", "1")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("JUDGE_OPENAI_MODEL", "gpt-test")
    judge, label = llm_judge.make_judge_llm()

    assert label == "openai:gpt-test"
    assert len(judge.providers) == 1
    assert judge.providers[0][0:2] == ("openai", "gpt-test")
    assert judge.providers[0][2].max_attempts == 1


def test_generation_failure_is_na_and_next_case_can_continue(monkeypatch):
    import llm_judge

    captured = []

    class FakeRunLog:
        def set_models(self, _models):
            pass

        def update(self, rows):
            captured[:] = [dict(row) for row in rows]

        def finish(self, _status, _error=None):
            pass

    class UnusedJudge:
        async def __call__(self, _prompt):
            raise AssertionError("생성 실패 케이스에서는 Judge를 호출하면 안 됨")

    async def failed_analysis(_case):
        return None, "SKIP: 고정 생성 모델 API 1회 호출 실패"

    rubric = {
        "criteria": [{"name": "정확성", "max_score": 100}],
        "verdict_thresholds": [{"min_score": 0, "verdict": "배포 보류"}],
        "immediate_hold_conditions": [],
    }
    monkeypatch.setenv("CROSS_VALIDATION_EXPERIMENT", "A")
    monkeypatch.setenv("GENERATION_PROVIDER", "openai")
    monkeypatch.setattr(llm_judge, "make_judge_llm", lambda: (UnusedJudge(), "anthropic:test"))
    monkeypatch.setattr(llm_judge, "get_analysis", failed_analysis)
    monkeypatch.setattr(llm_judge, "load_json", lambda _name: rubric)
    monkeypatch.setattr(llm_judge, "_write_reports", lambda *_args: None)

    case = {
        "case_id": "TC-X",
        "question": "테스트",
        "judge_enabled": True,
        "judge_mode": "live",
    }
    result = asyncio.run(llm_judge._run_judge([case], FakeRunLog()))

    assert result == 0
    assert captured[0]["total"] == "N/A"
    assert captured[0]["verdict"] == "미평가(파이프라인 실패)"
    assert captured[0]["api_attempts"] == "생성 파이프라인 실패, 대체 없음"


def test_comparison_report_contains_case_detail_and_graph_csv(tmp_path, monkeypatch):
    import cross_validation

    monkeypatch.setattr(cross_validation, "REPORT_ROOT", tmp_path)
    fields = [
        "case_id", "question", "total", "verdict", "immediate_hold",
        "pipeline_seconds", "judge_seconds", "total_seconds", "judge_model",
        "api_attempts", *cross_validation.CRITERIA_NAMES, "rationale",
    ]
    sample = {
        "case_id": "TC-01",
        "question": "테스트 질문",
        "total": "82",
        "verdict": "조건부 배포 가능",
        "immediate_hold": "False",
        "pipeline_seconds": "20.1",
        "judge_seconds": "5.2",
        "total_seconds": "25.3",
        "judge_model": "anthropic:test",
        "api_attempts": "anthropic:성공",
        **{name: "8" for name in cross_validation.CRITERIA_NAMES},
        "rationale": "채점 근거",
    }
    a_dir = tmp_path / "a"
    a_dir.mkdir()
    with (a_dir / "llm_judge_result.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerow(sample)

    cross_validation._update_comparison_report()

    report = (tmp_path / "교차검증_종합비교보고서.md").read_text(encoding="utf-8")
    assert "TC-01~20 실험군 교차 비교" in report
    assert "평가 항목별 평균 비교" in report
    assert "실험군 A 케이스별 채점·실패 근거" in report
    assert "TC-20" in report
    with (tmp_path / "교차검증_그래프데이터.csv").open(
        encoding="utf-8-sig", newline=""
    ) as file:
        graph_rows = list(csv.DictReader(file))
    assert len(graph_rows) == 1
    assert graph_rows[0]["experiment"] == "A"
    assert graph_rows[0]["case_id"] == "TC-01"
    assert graph_rows[0]["total"] == "82"
