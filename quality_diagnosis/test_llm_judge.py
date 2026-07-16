# =============================================
# File: quality_diagnosis/test_llm_judge.py
# =============================================
# LLM Judge 단위 테스트
# API 호출 없이 프롬프트 생성, 루브릭 검증, 응답 파싱, 판정 로직을 점검합니다.
#
# 실행: pytest quality_diagnosis/test_llm_judge.py -v

import pytest
from judge_prompt import build_judge_prompt, decide_verdict, parse_judge_response
from qa_test_utils import load_json


@pytest.fixture(scope="module")
def rubric():
    return load_json("judge_rubric.json")


def test_rubric_total_is_100(rubric):
    """루브릭 배점 합계가 100점인가."""
    assert sum(c["max_score"] for c in rubric["criteria"]) == 100
    assert rubric["total_max_score"] == 100


def test_rubric_has_nine_agent_criteria(rubric):
    """발표 평가표의 에이전트별 9개 기준이 그대로 적용되었는가."""
    names = [c["name"] for c in rubric["criteria"]]
    assert names == [
        "Interpreter 해석 정확성", "Retriever 검색 관련성", "Summarizer 사실성·요약성",
        "Evaluator 평가 타당성", "Critic 위험 탐지력", "Improver 실행 가능성",
        "Agent 연계 품질", "장애 대응·로그", "성능",
    ]


def test_judge_cases_loadable():
    """단일 test_cases.json에서 Judge 대상과 장애 대상을 구분할 수 있는가."""
    cases = load_json("test_cases.json")["cases"]
    assert len(cases) == 20
    assert [case["case_id"] for case in cases] == [f"TC-{number:02d}" for number in range(1, 21)]
    for c in cases:
        assert c["judge_mode"] in ("live", "static", "pytest_fault")
        assert isinstance(c["judge_enabled"], bool)
        assert c["question"]
        if c["judge_mode"] == "static":
            assert c.get("analysis"), f"{c['case_id']}: static 케이스에 analysis가 없습니다"
    assert sum(case["judge_enabled"] for case in cases) == 18


def test_build_judge_prompt_contains_inputs(rubric):
    """프롬프트에 질문, 분석 결과, 채점 기준이 모두 포함되는가."""
    prompt = build_judge_prompt("결제 오류 불만", "요약: 결제 실패 다수", rubric)
    assert "결제 오류 불만" in prompt
    assert "요약: 결제 실패 다수" in prompt
    for c in rubric["criteria"]:
        assert c["name"] in prompt
    assert "JSON" in prompt


def test_parse_judge_response_valid(rubric):
    """정상 JSON 응답이 올바르게 파싱되는가."""
    scores = {criterion["name"]: criterion["max_score"] for criterion in rubric["criteria"]}
    import json
    raw = json.dumps({"scores": scores, "total": 100, "immediate_hold": False,
                      "hold_reason": "", "rationale": "전반적으로 충실함"}, ensure_ascii=False)
    result = parse_judge_response(raw, rubric)
    assert result is not None
    assert result["total"] == 100
    assert result["immediate_hold"] is False


def test_parse_judge_response_clips_overflow(rubric):
    """항목 배점을 초과한 점수는 배점으로 잘라내고 total을 재계산하는가."""
    import json
    raw = json.dumps({"scores": {criterion["name"]: 999 for criterion in rubric["criteria"]}} , ensure_ascii=False)
    result = parse_judge_response(raw, rubric)
    assert result["scores"]["Interpreter 해석 정확성"] == 15
    assert result["total"] == 100


def test_parse_judge_response_invalid_returns_none(rubric):
    """JSON이 아니거나 scores가 없으면 None을 반환하는가."""
    assert parse_judge_response("채점할 수 없습니다.", rubric) is None
    assert parse_judge_response('{"foo": 1}', rubric) is None


@pytest.mark.parametrize("total,hold,expected", [
    (95, False, "배포 가능"),
    (85, False, "조건부 배포 가능, 개선 후 재검증"),
    (75, False, "주요 개선 필요"),
    (50, False, "배포 보류"),
    (95, True, "배포 보류(즉시)"),
])
def test_decide_verdict(rubric, total, hold, expected):
    """점수 구간·즉시보류 조건에 따라 판정이 올바른가."""
    assert decide_verdict(total, hold, rubric) == expected


def test_llm_judge_module_importable():
    """llm_judge.py가 임포트 가능하고 핵심 함수가 존재하는가. (API 호출 없음)"""
    import llm_judge
    assert callable(llm_judge.make_judge_llm)
    assert callable(llm_judge.main)


def test_judge_empty_row_preserves_stage_timings(rubric):
    """미평가·장애 케이스도 파이프라인·Judge·전체 시간이 기록되는가."""
    import llm_judge

    names = [criterion["name"] for criterion in rubric["criteria"]]
    row = llm_judge._empty_row(
        "TC-X", "live", "test:model", names, "미평가", "테스트",
        pipeline_seconds=12.3, judge_seconds=4.5, total_seconds=16.8,
    )
    assert row["pipeline_seconds"] == 12.3
    assert row["judge_seconds"] == 4.5
    assert row["total_seconds"] == 16.8
