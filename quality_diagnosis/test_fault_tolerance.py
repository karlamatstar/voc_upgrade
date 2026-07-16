# =============================================
# File: quality_diagnosis/test_fault_tolerance.py
# =============================================
# 장애·예외 처리 테스트
# 빈 질문, 존재하지 않는 CSV, 서버 중단 등 비정상 상황에서
# 시스템이 오류를 숨기지 않고 안전하게 처리하는지 점검합니다.
#
# 대부분 서버 없이 실행 가능하며, MCP 도구 폴백 동작을 함께 검증합니다.
#
# 실행: pytest quality_diagnosis/test_fault_tolerance.py -v

import pytest
from qa_test_utils import ROOT, is_port_open, pb2_generated, run_async

# utils.tools는 mcp 패키지가 필요하므로 없으면 관련 테스트 스킵
tools = pytest.importorskip("utils.tools", reason="mcp 패키지가 설치되어 있지 않습니다")


def test_health_check_missing_csv():
    """존재하지 않는 CSV 경로를 점검하면 ok=False로 명확히 알려주는가."""
    out = run_async(tools.health_check(csv_path=str(ROOT / "no_such_file.csv")), timeout=30)
    assert out["ok"] is False, "없는 파일인데 ok=True로 응답했습니다 (장애 은폐)"


def test_health_check_valid_csv():
    """정상 CSV 경로는 ok=True와 파일 크기를 반환하는가."""
    out = run_async(tools.health_check(csv_path=str(ROOT / "voc.csv")), timeout=30)
    assert out["ok"] is True
    assert out.get("size"), "파일 크기 정보가 없습니다"


def test_extract_keywords_empty_input():
    """빈 질문에서도 키워드 추출이 예외 없이 동작하는가."""
    assert tools.extract_keywords("") == []
    assert tools.extract_keywords(None) == []


def test_extract_keywords_removes_stopwords():
    """불용어(분석, 해주세요 등)는 키워드에서 제외되는가."""
    kw = tools.extract_keywords("결제 관련 불만 분석 해주세요")
    assert "분석" not in kw
    assert "해주세요" not in kw
    assert "결제" in kw


def test_parse_filters_handles_none():
    """filters가 None이어도 안전하게 처리되는가."""
    from utils.utils import parse_filters
    assert parse_filters(None) in (None, [])


@pytest.mark.skipif(not pb2_generated(), reason="voc_pb2.py 미생성")
def test_analyze_voc_returns_error_dict_when_servers_down():
    """에이전트 서버가 꺼진 상태에서 analyze_voc가 예외 대신 오류 딕셔너리를 반환하는가.

    (장애를 숨기지 않되, MCP 클라이언트가 죽지 않도록 안전하게 실패해야 함)
    """
    if is_port_open(6003):
        pytest.skip("Summarizer(6003)가 켜져 있어 서버 다운 시나리오를 재현할 수 없습니다")
    out = run_async(tools.analyze_voc(filters="결제", task="summary", max_items=10), timeout=60)
    assert isinstance(out, dict), "예외가 아닌 딕셔너리로 응답해야 합니다"
    assert out.get("ok") is False, "서버가 꺼져 있는데 성공으로 응답했습니다 (장애 은폐)"
    assert out.get("error"), "오류 원인(error)이 비어 있어 추적이 불가능합니다"


@pytest.mark.skipif(not pb2_generated(), reason="voc_pb2.py 미생성")
def test_analyze_voc_nl_v2_empty_question_safe():
    """빈 질문이 들어와도 예외 대신 안전한 결과/오류를 반환하는가."""
    out = run_async(tools.analyze_voc_nl_v2(question=""), timeout=200)
    assert isinstance(out, dict), "빈 질문 입력 시에도 딕셔너리로 응답해야 합니다"
    # 서버 가동 여부에 따라 성공(기본값 진행) 또는 실패(오류 명시) 둘 다 허용하되
    # 실패라면 반드시 원인을 남겨야 함
    if not out.get("ok", False):
        assert out.get("error"), "실패했는데 오류 원인이 없습니다"


@pytest.mark.skipif(not pb2_generated(), reason="voc_pb2.py 미생성")
def test_pipeline_missing_csv_not_silent_success():
    """존재하지 않는 CSV로 파이프라인 실행 시 조용히 성공 처리하지 않는가. (TC-20)"""
    out = run_async(
        tools.analyze_voc(filters="배송", task="summary", max_items=10,
                          csv_path=str(ROOT / "ghost.csv")),
        timeout=200,
    )
    assert isinstance(out, dict)
    if out.get("ok"):
        # 성공으로 응답했다면 최소한 데이터 없음이 요약에 드러나야 함
        summary = out.get("summary") or out.get("요약") or ""
        assert not summary or "없" in summary or "오류" in summary or "실패" in summary, (
            "없는 CSV인데 정상 요약을 생성했습니다 (데이터 오류 은폐)"
        )
