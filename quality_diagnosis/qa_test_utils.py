# =============================================
# File: quality_diagnosis/qa_test_utils.py
# =============================================
# QA 테스트 코드와 기존 프로젝트(에이전트/gRPC/MCP)를 연결하는 보조 모듈
#
# 주요 역할:
# - 프로젝트 루트 경로를 sys.path에 추가하여 utils/, agents/ 임포트 보장
# - 테스트 케이스(JSON) 로딩
# - 6개 에이전트 gRPC 포트(6001~6006) 가동 여부 확인
# - gRPC 파이프라인 실행 헬퍼 (grpc_server.VOCGRPCRuntime 래핑)

from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============ 프로젝트 루트 경로 설정 ============
# 이 파일은 <프로젝트루트>/quality_diagnosis/ 안에 있으므로 한 단계 위가 루트입니다
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 프로젝트 루트의 .env 파일(API 키 등)을 환경변수로 로딩
from utils.env_loader import load_env  # noqa: E402
load_env()

QA_DIR = Path(__file__).resolve().parent
REPORTS_DIR = QA_DIR / "reports"

# ============ 에이전트 포트 정의 ============
AGENT_PORTS = {
    "interpreter": 6001,
    "retriever": 6002,
    "summarizer": 6003,
    "evaluator": 6004,
    "critic": 6005,
    "improver": 6006,
}

# 6개 에이전트 소스 파일과 반드시 존재해야 하는 심볼
AGENT_FILES = {
    "interpreter": ("agents/interpreter.py", ["NLInterpreterAgent", "InterpreterServicer", "serve"]),
    "retriever": ("agents/retriever.py", ["RetrieverAgent", "RetrieverServicer", "serve"]),
    "summarizer": ("agents/summarizer.py", ["SummarizerAgent", "SummarizerServicer", "serve"]),
    "evaluator": ("agents/evaluator.py", ["EvaluatorAgent", "EvaluatorServicer", "serve"]),
    "critic": ("agents/critic.py", ["CriticAgent", "CriticServicer", "serve"]),
    "improver": ("agents/improver.py", ["PolicyImproverAgent", "ImproverServicer", "serve"]),
}


def load_json(filename: str) -> Any:
    """quality_diagnosis 폴더 안의 JSON 파일을 로드합니다."""
    with open(QA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def load_test_cases() -> List[Dict[str, Any]]:
    """test_cases.json의 테스트 케이스 목록을 반환합니다."""
    return load_json("test_cases.json")["cases"]


def load_expected_results() -> Dict[str, Any]:
    """test_cases.json에 함께 저장된 기대 결과를 case_id 기준으로 반환합니다."""
    return {case["case_id"]: case for case in load_test_cases()}


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    """지정한 포트에 TCP 연결이 가능한지 확인합니다."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def running_agents() -> Dict[str, bool]:
    """6개 에이전트 각각의 포트 가동 여부를 반환합니다."""
    return {name: is_port_open(port) for name, port in AGENT_PORTS.items()}


def all_agents_running() -> bool:
    """6개 에이전트가 모두 가동 중이면 True."""
    return all(running_agents().values())


def pb2_generated() -> bool:
    """voc_pb2.py / voc_pb2_grpc.py가 생성되어 있는지 확인합니다."""
    return (ROOT / "voc_pb2.py").exists() and (ROOT / "voc_pb2_grpc.py").exists()


def get_runtime():
    """grpc_server.VOCGRPCRuntime 인스턴스를 반환합니다 (pb2 파일 필요)."""
    import grpc_server  # noqa: PLC0415 - 지연 임포트 (pb2 미생성 시 임포트 에러 방지)
    return grpc_server.VOCGRPCRuntime()


def run_async(coro, timeout: float = 240.0):
    """비동기 코루틴을 동기 테스트에서 실행하는 헬퍼."""
    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


def run_pipeline_with_question(question: str, csv_path: Optional[str] = None,
                               timeout: float = 180.0) -> Dict[str, Any]:
    """자연어 질문으로 전체 파이프라인(Interpreter→...→Improver)을 실행합니다."""
    rt = get_runtime()
    return run_async(rt.run_with_question(question=question, csv_path=csv_path, timeout=timeout))


def run_pipeline_with_params(filters: Optional[List[str]], task: str = "both",
                             max_items: int = 30, csv_path: Optional[str] = None,
                             timeout: float = 180.0) -> Dict[str, Any]:
    """파라미터 지정 방식으로 파이프라인을 실행합니다."""
    rt = get_runtime()
    return run_async(rt.run_with_params(
        filters=filters, task=task, max_items=max_items,
        csv_path=csv_path or str(ROOT / "voc.csv"), timeout=timeout,
    ))


def contains_any(text: str, keywords: List[str]) -> bool:
    """텍스트에 키워드 중 하나라도 포함되면 True."""
    return any(k in text for k in keywords)


def contains_none(text: str, keywords: List[str]) -> bool:
    """텍스트에 금지 키워드가 하나도 없으면 True."""
    return not any(k in text for k in keywords)
