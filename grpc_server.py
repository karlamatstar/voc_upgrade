# ================================================
# File: grpc_server.py
# Role: A2A VOC Orchestrator (gRPC 기반 클라이언트)
# ================================================

# ============ 표준 라이브러리 및 타입 힌트 ============
# Python 3.7+ 호환성을 위한 annotations 가져오기 (타입 힌트 지연 평가)
from __future__ import annotations
# 운영체제 관련 기능 (환경변수 읽기 등)
import os
# JSON 데이터 직렬화/역직렬화
import json
# 정규표현식 (원본 질문에서 안전망용 키워드 토큰 추출)
import re
# 단계 및 전체 수행시간 측정
import time
# 타입 힌트를 위한 타입 정의들
from typing import Dict, Any, Optional, List
# gRPC 라이브러리 (비동기 클라이언트/서버 통신)
import grpc
# Protocol Buffers로 생성된 메시지 및 서비스 정의
import voc_pb2
import voc_pb2_grpc

# ============ 프로젝트 내부 모듈 임포트 ============
# settings.py에서 기본 CSV 경로를 불러오는 방식으로 통일
# 이렇게 하면 CSV 경로 설정이 한 곳에서 관리됩니다
from utils.settings import DEFAULT_CSV

# ============ gRPC 에이전트 엔드포인트 설정 ============
# 각 에이전트 서비스의 네트워크 주소를 환경변수에서 읽어옵니다
# 환경변수가 없으면 기본값(localhost)을 사용합니다
# 각 에이전트는 독립적인 포트에서 실행됩니다
INTERPRETER_ENDPOINT = os.environ.get("INTERPRETER_ENDPOINT", "localhost:6001")  # 자연어 질의 해석 서비스
RETRIEVER_ENDPOINT   = os.environ.get("RETRIEVER_ENDPOINT",   "localhost:6002")  # VOC 데이터 검색 서비스
SUMMARIZER_ENDPOINT  = os.environ.get("SUMMARIZER_ENDPOINT",  "localhost:6003")  # 요약 생성 서비스
EVALUATOR_ENDPOINT   = os.environ.get("EVALUATOR_ENDPOINT",   "localhost:6004")  # 요약 평가 서비스
CRITIC_ENDPOINT      = os.environ.get("CRITIC_ENDPOINT",      "localhost:6005")  # 요약/정책 비평 서비스
IMPROVER_ENDPOINT    = os.environ.get("IMPROVER_ENDPOINT",    "localhost:6006")  # 정책 개선안 생성 서비스


# ============ 원본 질문 안전망 토큰 추출 ============
_TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+")
_FALLBACK_STOPWORDS = {
    "정책", "개선안", "제시", "방안", "요청", "voc", "관련", "중심", "분석",
    "데이터", "해줘", "해주세요", "좀", "합니다", "습니다", "있습니다", "없습니다",
}
# 흔한 한국어 조사 접미사. 형태소 분석기가 아니라 단순 규칙이라 완벽하지
# 않지만, "앱을" -> "앱"처럼 CSV 원문(보통 "앱에서", "앱이" 등 다른 조사를
# 씀)과 어긋나는 것을 줄여준다. 긴 조사부터 먼저 검사해야 짧은 조사가
# 먼저 걸려 잘못 잘리는 것을 막을 수 있다(길이 내림차순 정렬).
_TRAILING_PARTICLES = sorted(
    ["으로부터", "에서부터", "이라도", "라도", "에서", "으로", "에게",
     "한테", "까지", "부터", "이나", "은", "는", "이", "가", "을",
     "를", "에", "도", "만", "의", "로", "나"],
    key=len, reverse=True,
)


def _strip_particle(token: str) -> str:
    """흔한 한국어 조사를 접미사로 간단히 제거한다(완벽한 형태소 분석은 아님).

    "앱을"(2글자)에서 "을"(1글자)을 떼면 "앱"(1글자)만 남는 것처럼, 결과가
    1글자여도 허용한다 - "앱"처럼 짧지만 유효한 도메인 명사가 실제로 많다.
    떼어낸 뒤 빈 문자열만 안 되면 된다(len(token) > len(particle)).
    """
    for particle in _TRAILING_PARTICLES:
        if len(token) > len(particle) and token.endswith(particle):
            return token[: -len(particle)]
    return token


def _extract_fallback_tokens(text: str, min_len: int = 2, max_cnt: int = 8) -> List[str]:
    """원본 질문에서 간단한 키워드 토큰을 뽑아 Retriever 안전망 필터로 쓴다.

    Interpreter가 매번 조금씩 다른 표현으로 필터를 뽑는 비결정성 때문에,
    같은 질문이어도 Retriever가 이따금 0건을 찾는 문제가 있었다. run_with_question이
    이 함수를 기본으로 쓰지는 않으며, 호출자가 extra_filters로 명시적으로 넘길 때만
    안전망이 적용된다(예: QA 스크립트가 "데이터 없음"이 정답이 아닌 케이스에서만 사용).

    조사가 안 떨어진 원형("앱을")과 조사를 뗀 형태("앱") 둘 다 후보로 넣어서,
    조사 제거 규칙이 틀리더라도 원형 매칭으로 보완되게 한다. 원형은 min_len(기본 2자)
    이상만 받지만, 조사를 뗀 결과는 1글자여도 허용한다(짧은 도메인 명사 보존).
    """
    tokens: List[str] = []

    def _add(tok: str, minimum: int) -> None:
        if len(tok) >= minimum and tok not in tokens:
            tokens.append(tok)

    for raw in _TOKEN_PATTERN.findall(text or ""):
        if raw in _FALLBACK_STOPWORDS:
            continue
        _add(raw, min_len)
        stripped = _strip_particle(raw)
        if stripped != raw and stripped not in _FALLBACK_STOPWORDS:
            _add(stripped, 1)
    return tokens[:max_cnt]


class VOCGRPCRuntime:
    """
    A2A VOC 전체 파이프라인 실행기
    MCP 서버에서 호출되는 인터페이스
    """

    # ============ 초기화 메서드 ============
    def __init__(self):
        # 각 에이전트는 모듈 상단의 INTERPRETER_ENDPOINT, SUMMARIZER_ENDPOINT 등 환경 변수 기반 상수를 사용합니다
        pass

    # ============ 자연어 기반 실행 메서드 ============
    # 사용자의 자연어 질의를 받아서 전체 VOC 분석 파이프라인을 실행합니다
    # 이 메서드는 Interpreter 에이전트를 먼저 호출하여 질의를 구조화된 파라미터로 변환합니다
    async def run_with_question(
        self,
        question: str,
        csv_path: Optional[str],
        timeout: float = 180.0,
        extra_filters: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        자연어 질의를 받아 VOC 분석 파이프라인을 실행합니다.

        Args:
            question: 사용자의 자연어 질의 (예: "상담 대기 시간 관련 불만 분석")
            csv_path: VOC 데이터 CSV 파일 경로 (None이면 기본값 사용)
            timeout: 각 gRPC 호출의 타임아웃 시간(초)
            extra_filters: Interpreter가 뽑은 필터에 추가로 얹을 안전망 필터 목록.
                기본값 None이면 기존과 동일하게 동작한다(실제 서비스 기본 경로는
                영향 없음). 호출자가 명시적으로 넘길 때만 Retriever 검색 범위가
                넓어진다 - 예: QA 스크립트가 "관련 데이터 없음"이 정답이 아닌
                케이스에서만 _extract_fallback_tokens(question) 결과를 넘긴다.

        Returns:
            Dict: 분석 결과 (summary, policy, trace 등 포함)
        """

        # CSV 경로 우선순위 결정:
        #   1순위: 사용자가 명시적으로 제공한 csv_path
        #   2순위: settings.py의 DEFAULT_CSV
        final_csv = csv_path or DEFAULT_CSV
        pipeline_started = time.perf_counter()

        # ============ 1단계: Interpreter 에이전트 호출 ============
        # 자연어 질의를 구조화된 파라미터(task, filters, max_items 등)로 변환합니다
        # insecure_channel은 TLS 없이 통신합니다 (로컬 개발 환경용)
        print("[파이프라인 1/6] Interpreter 진행 중...", flush=True)
        interpreter_started = time.perf_counter()
        async with grpc.aio.insecure_channel(INTERPRETER_ENDPOINT) as ch:
            # gRPC 스텁 생성 (서버의 메서드를 호출할 수 있는 클라이언트 객체)
            stub = voc_pb2_grpc.InterpreterStub(ch)
            # ParseQuestion RPC 호출: 자연어 질의를 파싱하여 구조화된 정보 추출
            res = await stub.ParseQuestion(
                voc_pb2.ParseQuestionReq(
                    question=question,      # 사용자의 자연어 질의
                    default_csv=final_csv   # 기본 CSV 경로 전달 (문자열 "default_csv" 방지)
                ), timeout=timeout  # 타임아웃 설정
            )
        interpreter_elapsed = time.perf_counter() - interpreter_started
        print(f"[파이프라인 1/6] Interpreter 완료 ({interpreter_elapsed:.2f}초)", flush=True)

        # ============ Intent 딕셔너리 구성 ============
        # Interpreter가 반환한 결과를 딕셔너리 형태로 정리합니다
        intent = {
            "task":      res.task or "both",           # 작업 유형: "summary", "policy", "both"
            "filters":   list(res.filters),            # 필터 키워드 리스트
            "max_items": res.max_items or 30,          # 최대 분석 항목 수 (기본값: 30)
            "csv_path":  res.csv_path or final_csv   # 최종 CSV 경로 (interpreter가 준 값 우선)
        }

        # ============ 안전망 필터 병합 ============
        # extra_filters가 있으면 Interpreter의 필터에 추가로 얹어서 검색 범위를
        # 넓힌다. intent["filters"]는 Interpreter가 실제로 뽑은 값 그대로
        # intent_json에 남겨 투명성을 유지하고, 실제 검색에는 combined_filters를 쓴다.
        combined_filters = list(intent["filters"])
        for tok in (extra_filters or []):
            if tok not in combined_filters:
                combined_filters.append(tok)

        # ============ Summarizer RunPipeline 직접 호출 ============
        # Interpreter에서 파싱된 intent를 사용하여 Summarizer의 RunPipeline을 호출합니다
        # Summarizer는 내부적으로 Retriever, Evaluator, Critic, Improver를 A2A 방식으로 호출하고
        # 최종 결과(summary, policy)를 반환합니다
        # 이렇게 하면 A2A 방식을 유지하면서도 최종 결과를 받을 수 있습니다
        async with grpc.aio.insecure_channel(SUMMARIZER_ENDPOINT) as ch:
            stub = voc_pb2_grpc.SummarizerStub(ch)
            sres = await stub.RunPipeline(
                voc_pb2.RunPipelineReq(
                    csv_path=intent["csv_path"],
                    filters=combined_filters,
                    max_items=intent["max_items"],
                    task=intent["task"],
                ),
                timeout=timeout
            )

        total_elapsed = time.perf_counter() - pipeline_started
        print(f"[파이프라인] 전체 분석 완료 ({total_elapsed:.2f}초)", flush=True)
        stage_trace = (
            f"Timing:Interpreter={interpreter_elapsed:.2f}s; "
            f"{sres.trace or ''}; Timing:TotalPipeline={total_elapsed:.2f}s"
        )
        return {
            "ok": sres.ok,
            "summary": sres.summary or "",
            "policy": sres.policy or "",
            "intent_json": json.dumps(intent, ensure_ascii=False),
            "eval_json": sres.eval_json or "{}",
            "summary_critic_json": sres.summary_critic_json or "{}",
            "trace": stage_trace,
            "message": "Pipeline completed via agent-to-agent calls",
        }

    # ============ 파라미터 기반 실행 메서드 ============
    # 자연어 질의 없이 직접 파라미터를 지정하여 VOC 분석을 수행합니다
    # 이 메서드는 Interpreter를 거치지 않고 바로 파이프라인을 실행합니다
    async def run_with_params(
        self,
        filters: Optional[List[str]],
        task: str,
        max_items: int,
        csv_path: str,
        timeout: float = 180.0
    ) -> Dict[str, Any]:
        """
        직접 파라미터를 지정하여 VOC 분석 파이프라인을 실행합니다.
        
        Args:
            filters: 필터링할 키워드 리스트 (None이면 필터링 없음)
            task: 수행할 작업 ("summary", "policy", "both")
            max_items: 분석할 최대 VOC 개수
            csv_path: VOC 데이터 CSV 파일 경로
            timeout: 각 gRPC 호출의 타임아웃 시간(초)
            
        Returns:
            Dict: 분석 결과 (summary, policy, trace 등 포함)
        """

        # CSV 경로 우선순위 결정
        final_csv = csv_path or DEFAULT_CSV

        # ============ Intent 딕셔너리 구성 ============
        # 사용자가 제공한 파라미터를 intent 딕셔너리로 구성합니다
        intent = {
            "task": task or "both",                    # 작업 유형 (기본값: "both")
            "filters": filters or [],                  # 필터 리스트 (None이면 빈 리스트)
            "max_items": max_items or 30,              # 최대 항목 수 (기본값: 30)
            "csv_path": final_csv,                     # CSV 경로
        }

        # ============ Summarizer RunPipeline 직접 호출 ============
        # A2A 방식을 유지하면서 결과를 받기 위해 Summarizer의 RunPipeline을 호출합니다
        # Summarizer는 내부적으로 Retriever, Evaluator, Critic, Improver를 A2A 방식으로 호출하고
        # 최종 결과(summary, policy)를 반환합니다
        async with grpc.aio.insecure_channel(SUMMARIZER_ENDPOINT) as ch:
            stub = voc_pb2_grpc.SummarizerStub(ch)
            sres = await stub.RunPipeline(
                voc_pb2.RunPipelineReq(
                    csv_path=final_csv,
                    filters=filters or [],
                    max_items=max_items,
                    task=task or "both",
                ),
                timeout=timeout
            )

        return {
            "ok": sres.ok,
            "summary": sres.summary or "",
            "policy": sres.policy or "",
            "intent_json": json.dumps(intent, ensure_ascii=False),
            "eval_json": sres.eval_json or "{}",
            "summary_critic_json": sres.summary_critic_json or "{}",
            "trace": sres.trace or "",
            "message": "Pipeline completed via agent-to-agent calls",
        }

