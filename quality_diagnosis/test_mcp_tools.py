# =============================================
# File: quality_diagnosis/test_mcp_tools.py
# =============================================
# MCP 도구 및 서버 연동 테스트
# main.py가 노출하는 MCP 도구(analyze_voc, analyze_voc_nl_v2, health_check 등)가
# 정상 등록되어 있고 호출 가능한지 점검합니다.
#
# 주의: analyze_voc 실호출 테스트는 6개 에이전트 서버가 켜져 있어야 하며,
#       꺼져 있으면 SKIP 처리됩니다.
#
# 실행: pytest quality_diagnosis/test_mcp_tools.py -v

import pytest
from qa_test_utils import ROOT, all_agents_running, pb2_generated, run_async, running_agents

tools = pytest.importorskip("utils.tools", reason="mcp 패키지가 설치되어 있지 않습니다")

# main.py의 MCP 서버가 반드시 노출해야 하는 도구 목록
REQUIRED_TOOLS = ["analyze_voc", "analyze_voc_nl_v2", "health_check"]
OPTIONAL_TOOLS = ["summarize_voc", "policy_from_summary"]


def _registered_tool_names():
    """FastMCP 인스턴스에 등록된 도구 이름 목록을 반환합니다."""
    tm = tools.mcp._tool_manager
    return list(tm._tools.keys())


def test_mcp_instance_exists():
    """main.py가 사용하는 FastMCP 인스턴스(voc_mcp)가 생성되어 있는가."""
    assert tools.mcp is not None
    assert tools.mcp.name == "voc_mcp"


@pytest.mark.parametrize("tool_name", REQUIRED_TOOLS)
def test_required_mcp_tool_registered(tool_name):
    """필수 MCP 도구가 서버에 등록되어 있는가."""
    assert tool_name in _registered_tool_names(), (
        f"MCP 도구 '{tool_name}'이 등록되어 있지 않습니다. 등록된 도구: {_registered_tool_names()}"
    )


@pytest.mark.parametrize("tool_name", OPTIONAL_TOOLS)
def test_optional_mcp_tool_registered(tool_name):
    """보조 MCP 도구(요약 전용, 정책 전용)가 등록되어 있는가."""
    assert tool_name in _registered_tool_names()


def test_main_py_runs_mcp_stdio():
    """main.py가 mcp를 임포트하고 stdio transport로 실행하도록 되어 있는가."""
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from utils.tools import mcp" in source
    assert 'transport="stdio"' in source or "transport='stdio'" in source


def test_health_check_tool_callable():
    """health_check 도구를 직접 호출하면 CSV 상태를 반환하는가. (서버 불필요)"""
    out = run_async(tools.health_check(), timeout=30)
    assert out["ok"] is True, f"기본 voc.csv 점검 실패: {out}"
    assert str(ROOT / "voc.csv").lower() in out["csv_path"].lower()


@pytest.mark.skipif(not pb2_generated(), reason="voc_pb2.py 미생성")
@pytest.mark.skipif(not all_agents_running(),
                    reason=f"에이전트 서버 미가동: {running_agents()}")
def test_analyze_voc_tool_end_to_end():
    """analyze_voc MCP 도구가 실제 파이프라인을 호출해 요약을 반환하는가."""
    out = run_async(tools.analyze_voc(filters="상담, 대기", task="summary", max_items=20),
                    timeout=240)
    assert out.get("ok"), f"analyze_voc 실패: {out}"
    assert out.get("summary") or out.get("요약"), "요약이 비어 있습니다"


@pytest.mark.skipif(not pb2_generated(), reason="voc_pb2.py 미생성")
@pytest.mark.skipif(not all_agents_running(),
                    reason=f"에이전트 서버 미가동: {running_agents()}")
def test_analyze_voc_nl_v2_tool_end_to_end():
    """analyze_voc_nl_v2 MCP 도구가 자연어 질문을 처리하는가."""
    out = run_async(
        tools.analyze_voc_nl_v2(question="상담 대기 시간 관련 불만을 요약해 주세요."),
        timeout=240,
    )
    assert out.get("ok"), f"analyze_voc_nl_v2 실패: {out}"
    assert out.get("summary") or out.get("요약"), "요약이 비어 있습니다"
