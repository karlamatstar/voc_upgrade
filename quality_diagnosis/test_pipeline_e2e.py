# =============================================
# File: quality_diagnosis/test_pipeline_e2e.py
# =============================================
# 6개 에이전트 전체 연결(E2E) 테스트
# 자연어 질문 → grpc_server.py → Interpreter → Retriever → Summarizer
# → Evaluator → Critic → Improver → 최종 결과 흐름을 점검합니다.
#
# 주의: 이 테스트는 6개 에이전트 gRPC 서버(6001~6006)가 모두 켜져 있어야 합니다.
#       서버가 꺼져 있으면 해당 테스트는 SKIP 처리됩니다.
#
# 실행: pytest quality_diagnosis/test_pipeline_e2e.py -v

import pytest
from qa_test_utils import (
    all_agents_running,
    pb2_generated,
    run_pipeline_with_params,
    running_agents,
)

# 서버 미가동 시 전체 스킵 사유 메시지
_SKIP_REASON = (
    "6개 에이전트 서버(6001~6006)가 모두 켜져 있어야 합니다. "
    f"현재 상태: {running_agents()}"
)

pytestmark = [
    pytest.mark.skipif(not pb2_generated(), reason="voc_pb2.py 미생성 - voc.proto를 먼저 컴파일하세요"),
    pytest.mark.skipif(not all_agents_running(), reason=_SKIP_REASON),
]

def test_pipeline_smoke_with_params():
    """파라미터 방식으로 파이프라인이 끝까지 완주하고 요약을 반환하는가."""
    out = run_pipeline_with_params(filters=["상담", "대기"], task="summary", max_items=20)
    assert out.get("ok"), f"파이프라인 실패: {out}"
    assert out.get("summary"), "요약(summary)이 비어 있습니다"


def test_pipeline_full_task_both():
    """task=both일 때 요약과 정책 개선안이 모두 생성되는가."""
    out = run_pipeline_with_params(filters=["불친절"], task="both", max_items=20)
    assert out.get("ok"), f"파이프라인 실패: {out}"
    assert out.get("summary"), "요약이 비어 있습니다"
    assert out.get("policy"), "정책 개선안(policy)이 비어 있습니다"


def test_pipeline_trace_shows_agent_chain():
    """trace에 에이전트 연계 정보가 남아 운영자가 추적 가능한가."""
    out = run_pipeline_with_params(filters=["상담"], task="summary", max_items=10)
    assert out.get("ok"), f"파이프라인 실패: {out}"
    assert out.get("trace"), "trace가 비어 있어 원인 추적이 불가능합니다"
